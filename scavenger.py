#!/usr/bin/env python3

import argparse
import copy
import gzip
import itertools
import logging
import math
import multiprocessing as mp
import os
import pysam
import random
import re
import shlex
import shutil
import string
import sys
import tempfile

from Bio import SeqIO
from collections import defaultdict
from intervaltree import IntervalTree
from subprocess import Popen, PIPE

from utils import run_aligner, build_aligner_index

LOGGER = logging.getLogger()
LOGGER.setLevel("INFO")

BIN_SIZE = 500
NUM_READ_PER_CHR = 1000


# Main function
def main(mp_fork, mp_spawn):
    parser = argparse.ArgumentParser(description="Scavenger", formatter_class=argparse.RawTextHelpFormatter)
    required_args = parser.add_argument_group("required arguments")
    add_args(parser, required_args)
    run_aligner.add_args(parser, required_args)
    parser_result = parser.parse_args()

    aligner = parser_result.aligner.lower()
    bam_output = parser_result.bam_output
    input_files = parser_result.input
    source_genome_files = parser_result.genome_file.split(",")
    genome_index = parser_result.genome_index
    parser_result.output_dir = parser_result.output_dir.rstrip("/")
    output_dir = parser_result.output_dir
    source_align_file = parser_result.source_align_file

    build_aligner_index.check_tools(aligner)
    run_aligner.check_tools(aligner)

    try:
        blast = Popen("blastn", stdout=PIPE, stderr=PIPE)
        blast.communicate()
    except Exception as e:
        print("[blastn] Error encountered when being called. Script will not run")
        print(e)
        sys.exit(1)

    if parser_result.prefix is None:
        prefix = os.path.splitext(os.path.basename(input_files[0]))[0].rstrip(".fastq").rstrip(".fq")
    else:
        prefix = parser_result.prefix

    if output_dir is None:
        output_prefix = prefix

        try:
            os.mkdir("rescue_data")
        except FileExistsError:
            pass

        try:
            os.mkdir("rescue_tmp")
        except FileExistsError:
            pass
    else:
        output_prefix = "%s/%s" % (output_dir, prefix)

        try:
            os.mkdir(output_dir)
        except FileExistsError:
            pass

        try:
            os.mkdir("%s/rescue_data" % output_dir)
        except FileExistsError:
            pass

        try:
            os.mkdir("%s/rescue_tmp" % output_dir)
        except FileExistsError:
            pass

    # Loggger file handler
    global LOGGER
    log_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %I:%M:%S %p")
    log_file_handler = logging.FileHandler("%s.log" % output_prefix, mode="w")
    log_file_handler.setFormatter(log_formatter)
    LOGGER.addHandler(log_file_handler)

    # Logger console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    LOGGER.addHandler(console_handler)

    # Source execution
    if source_align_file is None:
        LOGGER.info("Source execution...")
        if genome_index is None:
            parser_result.genome_index = build_aligner_index.build_index(parser_result)

        source_align_file = run_aligner.run_aligner(parser_result)
        LOGGER.info("Completed source execution")

    if len(parser_result.input) == 2:
        raise NotImplementedError("Paired-end read recovery not yet supported.")

    mapped_reads, unmapped_reads, count_summary = get_mapped_and_unmapped_reads(source_align_file)

    num_mapped_reads, num_unmapped_reads, num_total_reads = \
        count_summary["mapped"], count_summary["unmapped"], count_summary["total"]

    LOGGER.info("Total number of input reads: %s" % format(num_total_reads, ",d"))
    LOGGER.info("Total number of mapped reads: %s" % format(num_mapped_reads, ",d"))
    LOGGER.info("Total number of unmapped reads: %s" % format(num_unmapped_reads, ",d"))
    LOGGER.info("Total number of unique seqs of unmapped reads: %s" % format(len(unmapped_reads), ",d"))

    # Gets new alignments and some counting values
    LOGGER.info("Running follow-up execution for rescuing...")
    new_alignments, count_mapped_unmapped, count_unique, count_all = \
        get_new_alignments(mp_fork, mp_spawn, mapped_reads, source_genome_files, parser_result, output_prefix,
                           source_align_file, unmapped_reads)
    LOGGER.info("Completed follow-up execution")

    log_rescued_info(num_unmapped_reads, count_mapped_unmapped, count_unique, count_all)

    LOGGER.info("Total number of input reads: %s" % format(num_total_reads, ",d"))
    LOGGER.info("Total number of mapped reads in source: %s" % format(num_mapped_reads, ",d"))
    LOGGER.info("Percentage of source mappability: %f" % (num_mapped_reads / num_total_reads * 100))

    new_total_mapped_reads = num_mapped_reads + count_all
    LOGGER.info("Total number of mapped reads after rescue: %s" % format(new_total_mapped_reads, ",d"))
    LOGGER.info("Percentage of new mappability: %f" % (new_total_mapped_reads / num_total_reads * 100))

    if bam_output:
        new_align_file = "%s_rescued.bam" % output_prefix
    else:
        new_align_file = "%s_rescued.sam" % output_prefix

    LOGGER.info("Writing new alignment file (%s)..." % new_align_file)
    with pysam.AlignmentFile(source_align_file) as f:
        if bam_output:
            g = pysam.AlignmentFile(new_align_file, "wb", template=f)
        else:
            g = pysam.AlignmentFile(new_align_file, "wh", template=f)

        h = pysam.AlignmentFile("%s_rescued_only.bam" % output_prefix, "wb", template=f)
        for r in f:
            if r.query_name not in new_alignments:
                g.write(r)

        for query_name in new_alignments.keys():
            for alignment in new_alignments[query_name]:
                g.write(alignment)
                h.write(alignment)

        g.close()
        h.close()
    LOGGER.info("Completed writing new alignment file")

    LOGGER.info("Rescue mission finished!")


def add_args(parser, required_args):
    required_args.add_argument("--genome_file", "-G",
                               dest="genome_file",
                               required=True,
                               help="Genome FASTA file")
    parser.add_argument("--genome_index", "-g",
                        dest="genome_index",
                        help="The pre-built genome index directory to be used by aligner")
    parser.add_argument("--annotation", "-a",
                        dest="annotation",
                        help="Annotation file to be used by index builder")
    parser.add_argument("--builder_extra_args", "-be",
                        dest="builder_extra_args",
                        default="",
                        nargs="?",
                        help="Extra argument to be passed to aligner index build")
    parser.add_argument("--consensus_threshold", "-c",
                        dest="consensus_threshold",
                        default=0.6,
                        type=float,
                        help="Consensus threshold (Default: %(default)s)")
    parser.add_argument("--blast_perc_identity",
                        dest="blast_identity",
                        default=84,
                        type=int,
                        help="The minimum percentage of identity for BLASTN (Default: %(default)s)")
    parser.add_argument("--blast_perc_query_coverage",
                        dest="blast_query_coverage",
                        default=65,
                        type=int,
                        help="The minimum percentage of query coverage for BLASTN (Default: %(default)s)")
    parser.add_argument("--repeat_db", "-r",
                        help="Location of index file for tandem repeat database, e.g. from RepBase")
    parser.add_argument("--source_align_file", "-sf",
                        dest="source_align_file",
                        help="The source SAM file")
    parser.add_argument("--new_align_file", "-nf",
                        dest="new_align_file",
                        help=argparse.SUPPRESS)
    parser.add_argument("--new_input", "-ni",
                        dest="new_input",
                        help=argparse.SUPPRESS)


# Returns a dict of unmapped reads and a set of mapped reads
def get_mapped_and_unmapped_reads(source_align_file):
    global LOGGER
    LOGGER.info("Extracting mapped and unmapped reads from source alignment file (%s)..." % source_align_file)

    mapped_reads = set()
    unmapped_reads = defaultdict(list)
    best_unmapped_read = {}
    count_summary = defaultdict(int)

    with pysam.AlignmentFile(source_align_file) as f:
        for r in f:
            if r.is_secondary or r.is_supplementary:
                continue

            if r.is_unmapped:
                count_summary["unmapped"] += 1
                current_quality_score = sum(r.query_qualities)

                best_query_name, best_query_quality_score = best_unmapped_read.get(r.query_sequence, (None, -1))
                if current_quality_score > best_query_quality_score:
                    best_unmapped_read[r.query_sequence] = (r.query_name, current_quality_score)

                    if best_query_name:
                        unmapped_reads[r.query_sequence].append(best_query_name)
                else:
                    unmapped_reads[r.query_sequence].append(r.query_name)
            else:
                count_summary["mapped"] += 1
                if r.get_tag("NH") == 1:
                    mapped_reads.add(r.query_name)

    for sequence, best_query in best_unmapped_read.items():
        unmapped_reads[sequence].append(best_query[0])

    best_unmapped_read.clear()
    count_summary["total"] = count_summary["mapped"] + count_summary["unmapped"]
    LOGGER.info("Completed extracting required info")

    return mapped_reads, unmapped_reads, count_summary


# Returns a dict of new alignments for the unmapped reads and some counting values
def get_new_alignments(mp_fork, mp_spawn, mapped_reads, source_genome_files, parser_result,
                       output_prefix, source_align_file, unmapped_reads):
    if parser_result.new_align_file is None:
        # Rebuilds aligner index and rerun alignment with new input and genome
        results = mp_fork.Queue()
        procs = []

        # Starts a process to write the new genome file and build the new aligner index
        proc = mp_fork.Process(target=build_follow_up_index,
                               args=(unmapped_reads, parser_result, len(unmapped_reads) * BIN_SIZE, results))
        proc.start()
        procs.append(proc)

        # Starts a process to write the new input file
        proc = mp_fork.Process(target=make_new_input,
                               args=(parser_result.input[0].split(","), mapped_reads, parser_result.output_dir,
                                     results))
        proc.start()
        procs.append(proc)

        while True:
            running = any(proc.is_alive() for proc in procs)

            while not results.empty():
                result = results.get()

                if len(result) == 1:
                    new_input = result
                else:
                    num_ref, new_aligner_index = result

            if not running:
                break

        mapped_reads.clear()
        new_align_file = run_follow_up_alignment(parser_result, new_aligner_index, new_input, num_ref)
    else:
        new_align_file = parser_result.new_align_file

    # Extracts mapped and unmapped reads that have alignment with each other
    art_aligned_mapped_reads, art_aligned_unmapped_reads = get_art_aligned_reads(new_align_file, unmapped_reads)
    count_mapped_unmapped = len(art_aligned_unmapped_reads)
    global LOGGER
    LOGGER.info("Total unmapped reads have alignment: %s" % format(count_mapped_unmapped, ",d"))

    unmapped_names = {}
    for seq in unmapped_reads.keys():
        unmapped_names[unmapped_reads[seq][-1]] = unmapped_reads[seq]
    unmapped_reads.clear()

    # Stores mapped and unmapped reads info from the source sam file
    mapped_reads_info, unmapped_reads_info = \
        make_read_info(source_align_file, art_aligned_mapped_reads, art_aligned_unmapped_reads)

    grouped_unmapped_reads = get_consensus_reads(mp_fork, parser_result, art_aligned_unmapped_reads, mapped_reads_info)
    mapped_reads_info.clear()

    if parser_result.repeat_db:
        new_grouped_unmapped_reads = get_new_unmapped_reads(grouped_unmapped_reads, unmapped_reads_info,
                                                            parser_result.repeat_db, output_prefix)
    else:
        new_grouped_unmapped_reads = grouped_unmapped_reads

    new_alignments, count_unique, count_all, failed_unmapped = \
        get_rescued_reads(mp_spawn, source_genome_files, new_grouped_unmapped_reads, unmapped_reads_info, parser_result,
                          source_align_file, unmapped_names)

    if failed_unmapped:
        failed_unmapped_file = "%s_failed.txt" % output_prefix

        with open(failed_unmapped_file, "w") as f:
            for query_name in failed_unmapped.keys():
                f.write("%s\t%s\n" % (query_name, failed_unmapped[query_name]))
        LOGGER.warning("%d out of the %d reads failed to be rescued due to failure in tool" %
                       (len(failed_unmapped), count_mapped_unmapped))
        LOGGER.warning("These reads' query names and sequences are stored in %s" % failed_unmapped_file)

    return new_alignments, count_mapped_unmapped, count_unique, count_all


# Builds the follow up aligner index
def build_follow_up_index(unmapped_reads, parser_result, genome_length, results):
    aligner = parser_result.aligner.lower()
    output_dir = parser_result.output_dir
    new_genome, num_ref = make_new_genome(unmapped_reads, output_dir, "unmapped_genome")

    if aligner == "star":
        parser_result.builder_extra_args = "--genomeChrBinNbits %d --genomeSAindexNbases %d" % \
                                           (min(18, int(math.log(genome_length / num_ref, 2))),
                                            min(14, int(math.log(genome_length, 2) / 2) - 1))
    parser_result.genome_file = "/".join(new_genome.split("/")[:-1]) if aligner == "bismark" else new_genome
    parser_result.annotation = None
    new_genome_index = build_aligner_index.build_index(parser_result)

    global LOGGER
    LOGGER.info("Waiting for new input files...")

    results.put((num_ref, new_genome_index))


# Creates a new genome file with unmapped reads, returns the file"s name and the genome"s length
def make_new_genome(unmapped_reads, output_dir, filename):
    global BIN_SIZE, NUM_READ_PER_CHR, LOGGER

    LOGGER.info("Making a new genome file with unmapped reads...")
    new_genome = get_file_new_name(filename, output_dir, "all.fa")

    chr_num = 0
    with open(new_genome, "w") as f:
        f.write(">ART_CHR_{}\n".format(chr_num))
        # STAR does not guarantee any ordering in BAM, so we need to sort to ensure consistent ordering between runs
        for index, sequence in enumerate(sorted(unmapped_reads.keys())):
            if NUM_READ_PER_CHR > 0 and (index % NUM_READ_PER_CHR == 0 and index != 0):
                chr_num += 1
                f.write("\n>ART_CHR_{}\n".format(chr_num))

            chromosome_bin = sequence + "N" * (BIN_SIZE - len(sequence))
            f.write(chromosome_bin)
        f.write("\n")

    LOGGER.info("Completed making new genome file")

    return new_genome, chr_num + 1


# Creates new input files with mapped reads only and returns the names of the files
def make_new_input(input_files, mapped_reads, output_dir, results):
    global LOGGER
    LOGGER.info("Making new input files with mapped reads only...")

    new_input = ""

    for input_file in input_files:
        if input_file.endswith(".gz"):
            f = gzip.open(input_file, "rt")
        else:
            f = open(input_file, "r")

        new_input_file = get_file_new_name(input_file, output_dir, "mapped.fq")
        new_input += ",%s" % new_input_file
        fq_reads = []

        while True:
            fq_read = list(itertools.islice(f, 4))

            if not fq_read:
                break

            query_name = fq_read[0].split("@")[-1].split(" ")[0].strip()

            if query_name in mapped_reads:
                fq_reads.append("".join(fq_read))

        f.close()

        with open(new_input_file, "w") as f:
            for fq_read in fq_reads:
                f.write(fq_read)

    new_input = re.sub("^,", "", new_input, 1)
    new_input = re.sub(" ,", " ", new_input, 1)
    new_input = new_input.strip().split(" ")

    LOGGER.info("Completed making new input files")

    results.put(new_input)


# Builds new index and aligns with new input and new genome and returns the name of the new sam file
def run_follow_up_alignment(parser_result, new_genome_index, new_input, num_ref):
    aligner = parser_result.aligner.lower()
    old_bam_output = parser_result.bam_output

    if aligner == "star":
        parser_result.aligner_extra_args = "--outFilterMultimapNmax %d --alignIntronMax 1 --seedSearchStartLmax 30" % \
                                           num_ref
    parser_result.genome_index = new_genome_index
    parser_result.input = new_input
    parser_result.bam_output = True
    new_align_file = run_aligner.run_aligner(parser_result)
    parser_result.bam_output = old_bam_output

    return new_align_file


# Returns a dict of list of unmapped reads that are aligned with mapped reads
# And their corresponded list of mapped reads
# And returns a set of mapped reads that have alignment with unmapped reads
def get_art_aligned_reads(new_align_file, unmapped_reads):
    global BIN_SIZE, NUM_READ_PER_CHR, LOGGER

    LOGGER.info("Reading new alignment file (%s)..." % new_align_file)

    art_aligned_unmapped_reads = defaultdict(list)
    art_aligned_mapped_reads = set()

    unmapped_reads_list = sorted(list(unmapped_reads.keys()))
    with pysam.AlignmentFile(new_align_file) as f:
        for r in f:
            if r.is_unmapped:
                continue

            query_name = r.query_name
            chr_num = int(r.reference_name.split("_")[-1])
            ref_alignment_loc = r.get_reference_positions()

            if len(ref_alignment_loc) < 2:
                print("Being passed due to position < 2?", query_name, ref_alignment_loc)
                continue

            ref_start_bin = ref_alignment_loc[0] // BIN_SIZE
            ref_end_bin = ref_alignment_loc[-1] // BIN_SIZE

            if ref_start_bin != ref_end_bin:  # Reads with unintended new junction
                continue

            reference_name = unmapped_reads[unmapped_reads_list[chr_num * NUM_READ_PER_CHR + ref_start_bin]][-1]
            art_aligned_unmapped_reads[reference_name].append(query_name)
            art_aligned_mapped_reads.add(query_name)

    LOGGER.info("Completed reading new alignment file")

    return art_aligned_mapped_reads, art_aligned_unmapped_reads


# Creates an index of the source sam file
def make_read_info(source_align_file, art_aligned_mapped_reads, art_aligned_unmapped_reads):
    global LOGGER
    LOGGER.info("Extracting info from source SAM file (%s)..." % source_align_file)

    mapped_reads_info = {}
    unmapped_reads_info = {}

    with pysam.AlignmentFile(source_align_file) as f:
        for r in f:
            if r.is_secondary or r.is_supplementary:
                continue

            query_name = r.query_name
            sequence = r.query_sequence
            is_spliced = False

            if not r.is_unmapped:
                if query_name in art_aligned_mapped_reads:
                    if "N" in r.cigarstring:
                        is_spliced = True

                    mapped_reads_info[query_name] = (r.reference_id, r.reference_start, r.reference_end,
                                                     r.mapping_quality, is_spliced)
            else:
                if query_name in art_aligned_unmapped_reads:
                    unmapped_reads_info[query_name] = (sequence, pysam.qualities_to_qualitystring(r.query_qualities))

    LOGGER.info("Completed info extraction")

    return mapped_reads_info, unmapped_reads_info


# Returns a dict using reference name as the key and store the unmapped reads that passed consensus check
def get_consensus_reads(mp_fork, parser_result, art_aligned_unmapped_reads, mapped_reads_info):
    global LOGGER
    LOGGER.info("Grouping consensus reads...")

    consensus_threshold = parser_result.consensus_threshold
    output_dir = parser_result.output_dir
    threads = parser_result.threads
    grouped_unmapped_reads = defaultdict(dict)
    count_passed_consensus = 0
    procs = []

    tasks = mp_fork.JoinableQueue()
    results = mp_fork.Queue()

    # Starts processing the tasks
    for _ in range(threads):
        proc = mp_fork.Process(target=check_reads_consensus,
                               args=(mapped_reads_info, consensus_threshold, tasks, results))
        proc.start()
        procs.append(proc)

    for item in art_aligned_unmapped_reads.items():
        tasks.put(item)

    for _ in range(threads):
        tasks.put(None)

    art_aligned_unmapped_reads.clear()

    # Waits for all processes to join
    tasks.join()

    while True:
        running = any(proc.is_alive() for proc in procs)

        while not results.empty():
            unmapped_name, target_list = results.get()

            if target_list:
                count_passed_consensus += 1

                for ref_id, start, end, is_spliced in target_list:
                    key = (start, end, is_spliced)
                    if key in grouped_unmapped_reads[ref_id]:
                        grouped_unmapped_reads[ref_id][key].append(unmapped_name)
                    else:
                        grouped_unmapped_reads[ref_id][key] = [unmapped_name]

        if not running:
            break

    LOGGER.info("Completed grouping consensus reads")
    LOGGER.info("Total unmapped aligned with mapped passed consensus: %s" % format(count_passed_consensus, ",d"))

    return grouped_unmapped_reads


# Checks for consensus info for potential rescue locations
def check_reads_consensus(mapped_reads_info, consensus_threshold, tasks, results):
    while True:
        item = tasks.get()

        if item is None:
            tasks.task_done()
            break

        unmapped_name, unmapped_read_mapped_list = item
        grouped_reads = defaultdict(list)
        mapped_locs = defaultdict(IntervalTree)
        ref_id_count = defaultdict(int)
        potential_ref_id = []
        target_scores = defaultdict(list)
        most_count_lists = defaultdict(list)
        target_reads = []

        # Pre-groups mapped reads that are mapped to the exact same locations
        for mapped_name in unmapped_read_mapped_list:
            ref_id, start, end, score, is_spliced = mapped_reads_info[mapped_name]
            grouped_reads[(ref_id, start, end)].append(mapped_name)

        # Builds a dict of reference names of interval tree
        for key in grouped_reads.keys():
            ref_id, start, end = key
            mapped_locs[ref_id].addi(start, end, grouped_reads[key])
            ref_id_count[ref_id] += len(grouped_reads[key])
        grouped_reads.clear()

        for ref_id in ref_id_count.keys():
            if (ref_id_count[ref_id] / len(unmapped_read_mapped_list)) >= consensus_threshold:
                potential_ref_id.append(ref_id)

        if len(potential_ref_id) == 0:
            results.put((unmapped_name, target_reads))
            tasks.task_done()
            continue

        # Merges identical intervals
        for ref_id in potential_ref_id:
            mapped_locs[ref_id].merge_overlaps(data_reducer=lambda x, y: x+y)

            for iv in mapped_locs[ref_id]:
                if len(iv.data) >= 2 and len(iv.data) / len(unmapped_read_mapped_list) >= consensus_threshold:
                    most_count_lists[len(iv.data)].append(iv.data)

        if most_count_lists:
            target_mapped_list = most_count_lists[max(most_count_lists.keys())]

            for data_list in target_mapped_list:
                mapped_name = sorted(data_list)[0]
                ref_id, start, end, score, is_spliced = mapped_reads_info[mapped_name]
                target_scores[score].append((ref_id, start, end, is_spliced))

            target_reads = target_scores[max(target_scores.keys())]

        results.put((unmapped_name, target_reads))
        tasks.task_done()


# Gets rescued reads' alignments
def get_rescued_reads(mp_spawn, source_genome_files, grouped_unmapped_reads, unmapped_reads_info, parser_result,
                      source_align_file, unmapped_names):
    global LOGGER
    LOGGER.info("Rescuing unmapped reads...")

    threads = parser_result.threads
    tasks = mp_spawn.JoinableQueue()
    results = mp_spawn.Queue()
    procs = []
    new_aligned_names = defaultdict(list)
    failed_unmapped = {}
    new_alignments = defaultdict(list)

    # Starts the processes
    for _ in range(threads):
        proc = mp_spawn.Process(target=rescue_reads,
                                args=(tasks, results, parser_result))
        proc.start()
        procs.append(proc)

    with pysam.AlignmentFile(source_align_file) as f:
        all_references = list(f.references)

    # Fills the tasks queue
    for genome_file in source_genome_files:
        if genome_file.endswith(".gz"):
            f = gzip.open(genome_file, "rt")
        else:
            f = open(genome_file, "r")

        for record in SeqIO.parse(f, "fasta"):
            genome_ref_id = all_references.index(record.id)

            if genome_ref_id in grouped_unmapped_reads:
                genome_seq = record.seq

                # Stores a target genome for each unmapped read
                for key in grouped_unmapped_reads[genome_ref_id]:
                    start, end, is_spliced = key
                    # unmapped_seq, unmapped_qual = unmapped_reads_info[unmapped_name]
                    # extend_len = len(unmapped_seq)
                    extend_len = 100

                    # Extracts a target genome with the info of where the mapped read was mapped
                    start -= extend_len
                    start = 0 if start < 0 else start
                    end += extend_len
                    end = len(genome_seq) if end > len(genome_seq) else end
                    target_genome_seq = genome_seq[start:end]

                    unmapped_info = {}
                    for unmapped_name in grouped_unmapped_reads[genome_ref_id][key]:
                        unmapped_seq, unmapped_qual = unmapped_reads_info[unmapped_name]
                        unmapped_info[unmapped_name] = unmapped_seq, unmapped_qual

                    tasks.put((unmapped_info, genome_ref_id, start, is_spliced, target_genome_seq))

        f.close()

    for _ in range(threads):
        tasks.put(None)

    grouped_unmapped_reads.clear()
    unmapped_reads_info.clear()
    tasks.join()

    while True:
        running = any(proc.is_alive() for proc in procs)

        while not results.empty():
            result = results.get()

            if len(result) == 2:
                unmapped_name, unmapped_seq = result
                failed_unmapped[unmapped_name] = unmapped_seq
            else:
                aligned_segment = pysam.AlignedSegment()
                aligned_segment.query_name, aligned_segment.flag, aligned_segment.reference_id, \
                    aligned_segment.reference_start, aligned_segment.mapping_quality, aligned_segment.cigarstring, \
                    aligned_segment.next_reference_id, aligned_segment.next_reference_start, \
                    aligned_segment.template_length, aligned_segment.query_sequence, aligned_segment.query_qualities, \
                    aligned_segment.tags = result
                new_aligned_names[aligned_segment.query_name].append(aligned_segment)

        if not running:
            break

    new_new_alignments = {}
    for new_name in new_aligned_names.keys():
        num_mapping = len(new_aligned_names[new_name])
        if num_mapping == 1:
            new_new_alignments[new_name] = new_aligned_names[new_name]

    for new_name in new_new_alignments.keys():
        for query_name in unmapped_names[new_name]:
            for alignment in new_new_alignments[new_name]:
                new_alignment = copy.deepcopy(alignment)
                new_alignment.query_name = query_name

                new_alignments[query_name].append(new_alignment)

    count_unique = len(new_new_alignments)
    count_all = len(new_alignments)

    LOGGER.info("Completed rescuing reads")

    return new_alignments, count_unique, count_all, failed_unmapped


# Rescues unmapped reads, returns some counting info and a list of the info of the new alignment
# New alignment will be length of 1 if no consensus, and length of 2 if the tools have failed to finish
def rescue_reads(tasks, results, parser_result):
    aligner = parser_result.aligner.lower()
    output_dir = parser_result.output_dir

    while True:
        item = tasks.get()

        if item is None:
            tasks.task_done()
            break

        unmapped_info, ref_id, start, is_spliced, genome_seq = item

        rescue_tmp_dir = output_dir + "/rescue_tmp"
        random_prefix = random_string(10)
        temp_dir = "%s/%s_temp" % (rescue_tmp_dir, random_prefix)
        random_output_prefix = "%s/%s" % (rescue_tmp_dir, random_prefix)
        target_sam_file = None

        unmapped_read_file, target_genome_file, star_index_num = \
            make_unmapped_read_target_genome(unmapped_info, ref_id, genome_seq, random_output_prefix, is_spliced)

        if is_spliced:
            # Rebuilds aligner index with target genome file
            if aligner == "star":
                parser_result.builder_extra_args = "--genomeSAindexNbases {star_index_num} " \
                                                   "--outTmpDir {temp_dir}".format(star_index_num=star_index_num,
                                                                                   temp_dir=temp_dir)
            parser_result.genome_file = target_genome_file
            parser_result.output_dir = rescue_tmp_dir
            parser_result.prefix = random_prefix
            parser_result.quiet = True
            parser_result.threads = 1
            try:
                target_genome_index = build_aligner_index.build_index(parser_result)
            except RuntimeError:
                for unmapped_name in unmapped_info:
                    unmapped_seq = unmapped_info[unmapped_name][0]
                    results.put((unmapped_name, unmapped_seq))
                tasks.task_done()
                continue

            # Aligns unmapped read to target genome
            if aligner == "star":
                parser_result.aligner_extra_args = "--outTmpDir %s" % temp_dir
            else:
                parser_result.aligner_extra_args = None
            parser_result.input = [unmapped_read_file]
            parser_result.genome_index = target_genome_index
            if target_genome_index is not None:
                try:
                    target_sam_file = run_aligner.run_aligner(parser_result)
                except RuntimeError:
                    for unmapped_name in unmapped_info:
                        unmapped_seq = unmapped_info[unmapped_name][0]
                        results.put((unmapped_name, unmapped_seq))
                    tasks.task_done()
                    continue
        else:
            target_sam_file = "%s.sam" % random_output_prefix
            command = "blastn -query {unmapped_read} -subject {target_genome} -task megablast -perc_identity {identity} " \
                      "-qcov_hsp_perc {coverage} -outfmt \"17 SQ SR\" -out {sam_output} -parse_deflines". \
                format(unmapped_read=unmapped_read_file,
                       target_genome=target_genome_file,
                       identity=parser_result.blast_identity,
                       coverage=parser_result.blast_query_coverage,
                       sam_output=target_sam_file)

            tool_process = Popen(shlex.split(command), stdout=PIPE, stderr=PIPE)
            tool_out, tool_err = tool_process.communicate()

            if tool_process.returncode != 0 or "[Errno" in tool_err.decode("utf8").strip():
                for unmapped_name in unmapped_info:
                    unmapped_seq = unmapped_info[unmapped_name][0]
                    results.put((unmapped_name, unmapped_seq))
                tasks.task_done()
                continue

        if os.path.exists(target_sam_file) and os.path.getsize(target_sam_file) != 0:
            # Checks for target genome results
            with pysam.AlignmentFile(target_sam_file) as f:
                for r in f:
                    if not r.is_unmapped and not r.is_secondary and not r.is_supplementary:
                        new_start = start + r.reference_start
                        cigarstring = r.cigarstring
                        first_hard_clip = re.findall("^\d+H", cigarstring)
                        first_bp = int(re.findall("\d+", first_hard_clip[0])[0]) if first_hard_clip else None
                        last_hard_clip = re.findall("\d+H$", cigarstring)
                        last_bp = int(re.findall("\d+", last_hard_clip[0])[0]) if last_hard_clip else None
                        unmapped_qual = unmapped_info[r.query_name][1]

                        if r.is_reverse:
                            new_qualities = pysam.qualitystring_to_array(unmapped_qual[::-1])
                        else:
                            new_qualities = pysam.qualitystring_to_array(unmapped_qual)

                        if first_bp is not None:
                            new_qualities = new_qualities[first_bp:]

                        if last_bp is not None:
                            last_bp = len(new_qualities) - last_bp
                            new_qualities = new_qualities[:last_bp]

                        results.put((r.query_name, r.flag, ref_id, new_start, r.mapping_quality, cigarstring,
                                     r.next_reference_id, r.next_reference_start, r.template_length,
                                     r.query_sequence, new_qualities, r.tags))
                        # break

        # Removes useless files and directories
        os.remove(unmapped_read_file)
        os.remove(target_genome_file)
        if os.path.exists("%s.sam" % random_output_prefix):
            os.remove("%s.sam" % random_output_prefix)
        elif os.path.exists("%s.bam" % random_output_prefix):
            os.remove("%s.bam" % random_output_prefix)

        if is_spliced and aligner == "star":
            if os.path.exists("%s.Aligned.out.sam" % random_output_prefix):
                os.remove("%s.Aligned.out.sam" % random_output_prefix)

            if os.path.exists("%s_star" % random_output_prefix):
                shutil.rmtree("%s_star" % random_output_prefix)

            if os.path.exists("%s_temp" % random_output_prefix):
                shutil.rmtree("%s_temp" % random_output_prefix)

            if os.path.exists("%s.Log.final.out" % random_output_prefix):
                os.remove("%s.Log.final.out" % random_output_prefix)

            if os.path.exists("%s.Log.out" % random_output_prefix):
                os.remove("%s.Log.out" % random_output_prefix)

            if os.path.exists("%s.Log.progress.out" % random_output_prefix):
                os.remove("%s.Log.progress.out" % random_output_prefix)

            if os.path.exists("%s.SJ.out.tab" % random_output_prefix):
                os.remove("%s.SJ.out.tab" % random_output_prefix)

        tasks.task_done()


# Makes the unmapped read file in fastq if spliced else in fasta
# And creates a target genome fasta file where the mapped read was mapped
# Returns the filename of the unmapped read and target genome files
# And a number for star index generation
def make_unmapped_read_target_genome(unmapped_info, ref_id, genome_seq,
                                     random_output_prefix, is_spliced):
    if is_spliced:
        unmapped_read_file = "%s_unmapped.fq" % random_output_prefix
    else:
        unmapped_read_file = "%s_unmapped.fa" % random_output_prefix

    input_entries = []

    if is_spliced:
        for unmapped_name in unmapped_info:
            unmapped_seq, unmapped_qual = unmapped_info[unmapped_name]
            input_entries.append("@%s\n%s\n+\n%s\n" % (unmapped_name, unmapped_seq, unmapped_qual))
    else:
        for unmapped_name in unmapped_info:
            unmapped_seq = unmapped_info[unmapped_name][0]
            input_entries.append(">%s\n%s\n" % (unmapped_name, unmapped_seq))

    with open(unmapped_read_file, "w") as f:
        for entry in input_entries:
            f.write(entry)

    # del input_entries[:]

    target_genome_file = "%s_genome.fa" % random_output_prefix

    with open(target_genome_file, "w") as f:
        f.write(">%s\n%s\n" % (ref_id, genome_seq))

    if len(genome_seq) <= 1000:
        star_index_num = 1
    else:
        star_index_num = min(14, round(math.log(len(genome_seq), 2) / 2 - 1))

    return unmapped_read_file, target_genome_file, star_index_num

####################
# Helper functions #
####################


def log_rescued_info(total_unmapped_reads, count_mapped_unmapped, count_unique, count_all):
    global LOGGER
    LOGGER.info("Total unmapped aligned with mapped: %s" % format(count_mapped_unmapped, ",d"))
    LOGGER.info("Total unique can map: %s" % format(count_unique, ",d"))

    if count_mapped_unmapped == 0:
        LOGGER.info("Percent unique can map: 0")
    else:
        LOGGER.info("Percent unique can map: %f" % (count_unique / count_mapped_unmapped * 100))

    LOGGER.info("Total all unmapped: %s" % format(total_unmapped_reads, ",d"))
    LOGGER.info("Total all can map: %s" % format(count_all, ",d"))

    if total_unmapped_reads == 0:
        LOGGER.info("Percent all can map: 0")
    else:
        LOGGER.info("Percent all can map: %f" % (count_all / total_unmapped_reads * 100))


# Returns a new filename attached with the given keyword
def get_file_new_name(file_name, output, keyword):
    new_name = "rescue_data/"
    new_name += file_name.split("/")[-1].split(".")[0]
    new_name += "_%s" % keyword

    if output is not None:
        new_name = "%s/%s" % (output, new_name)

    return new_name


# Creates random string with the given length
def random_string(length):
    return "".join(random.choice(string.ascii_letters) for _ in range(length))


def get_new_unmapped_reads(grouped_unmapped_reads, unmapped_info, repeat_db, output_prefix):
    unmapped_names = set()
    for ref_id in grouped_unmapped_reads:
        for loc in grouped_unmapped_reads[ref_id]:
            unmapped_names.update(set(grouped_unmapped_reads[ref_id][loc]))

    input_entries = []
    for unmapped_name in unmapped_names:
        unmapped_seq = unmapped_info[unmapped_name][0]
        input_entries.append(">%s\n%s\n" % (unmapped_name, unmapped_seq))

    with tempfile.NamedTemporaryFile() as tmp_input, tempfile.NamedTemporaryFile() as tmp_output, \
            open(tmp_input.name, "w") as f:
        for entry in input_entries:
            f.write(entry)

        command = "blastn -db {repeat_db} -query {input_fa} -task megablast -perc_identity 90 " \
                  "-qcov_hsp_perc 80 -outfmt \"17 SQ SR\" -out {sam_output} -parse_deflines -evalue 0.00001". \
            format(repeat_db=repeat_db,
                   input_fa=tmp_input.name,
                   sam_output=tmp_output.name)

        tool_process = Popen(shlex.split(command), stdout=PIPE, stderr=PIPE)
        tool_out, tool_err = tool_process.communicate()

        if tool_process.returncode != 0 or "[Errno" in tool_err.decode("utf8").strip():
            raise RuntimeError("Something went wrong\nstdout:{}\nstderr:{}\n".format(tool_out, tool_err))

        filtered_ids = set()
        if os.path.getsize(tmp_output.name) != 0:
            with pysam.AlignmentFile(tmp_output.name) as g:
                for r in g:
                    if not r.is_unmapped:
                        filtered_ids.add(r.query_name)

    with open("{}_filtered_ids.txt".format(output_prefix), "w") as f:
        for filtered_id in filtered_ids:
            f.write(filtered_id + "\n")

    new_grouped_unmapped_reads = defaultdict(dict)
    for ref_id in grouped_unmapped_reads:
        for loc in grouped_unmapped_reads[ref_id]:
            for unmapped_name in grouped_unmapped_reads[ref_id][loc]:
                if unmapped_name not in filtered_ids:
                    if loc in new_grouped_unmapped_reads[ref_id]:
                        new_grouped_unmapped_reads[ref_id][loc].append(unmapped_name)
                    else:
                        new_grouped_unmapped_reads[ref_id][loc] = [unmapped_name]

    return new_grouped_unmapped_reads


if __name__ == "__main__":
    main(mp.get_context("fork"), mp.get_context("spawn"))
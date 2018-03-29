import argparse
import logging
import os
import re
import shlex
import sys
from subprocess import Popen, PIPE


def main():
    parser = argparse.ArgumentParser(description="RNA-Seq Aligner")
    required_args = parser.add_argument_group('required arguments')
    add_args(parser, required_args)
    parser.set_defaults(method=run_aligner)

    parser_result = parser.parse_args()
    parser_result.method(**vars(parser_result))


def run_aligner(aligner, genome_index, input_files, output_dir, prefix, num_threads, aligner_extra_args, bam_output,
                clean_files, quiet, **kwargs):
    check_tools(aligner)

    # Check for valid number of inputs
    if len(input_files) > 2:
        error = "Invalid input, input takes at most 2 arguments.\n" \
                "Example: --input/-i /path/to/read1 [/path/to/read2] " \
                "(e.g. a1.fq,b1.fq a2.fq,b2.fq)\n" \
                "Your input: %s" % " ".join(input_files)
        raise argparse.ArgumentTypeError(error)

    # Check for number of each paired end input is the same
    elif (len(input_files) == 2 and
          len(input_files[0].split(",")) != len(input_files[1].split(","))):
        error = "Invalid input, the number of read1 does not equal to that of read2\n" \
                "You input: %s" % " ".join(input_files)
        raise argparse.ArgumentTypeError(error)

    # Set prefix from first input file
    if prefix is None:
        prefix = os.path.splitext(os.path.basename(input_files[0].split(",")[0]))[0]. \
            rstrip(".fastq").rstrip(".fq")

    # Create output directory
    try:
        os.mkdir(output_dir)
    except FileExistsError:
        pass

    root_logger = log_file_handler = None
    if not quiet:
        # Setup root logger
        log_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt='%Y-%m-%d %I:%M:%S %p')
        root_logger = logging.getLogger()
        root_logger.setLevel("INFO")

        # Setup file logger
        log_file_handler = logging.FileHandler("{}/{}_aligner.log".format(output_dir, prefix))
        log_file_handler.setFormatter(log_formatter)
        root_logger.addHandler(log_file_handler)

        # Setup stdout logger
        if len(root_logger.handlers) == 1:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(log_formatter)
            root_logger.addHandler(console_handler)

        tools_names = {"star": "STAR", "subread": "Subread"}
        root_logger.info("Aligning reads using %s..." % tools_names[aligner])

    output_prefix = "{}/{}".format(output_dir, prefix)
    if aligner == "star":
        out_sam_file = run_star(genome_index, input_files, output_prefix, num_threads, aligner_extra_args, bam_output,
                                clean_files, root_logger, quiet)
    elif aligner == "subread":
        out_sam_file = run_subread(genome_index, input_files, output_prefix, num_threads, aligner_extra_args,
                                   bam_output, root_logger, quiet)
    else:
        out_sam_file = None

    if not quiet:
        root_logger.info("Completed reads alignment")
        root_logger.removeHandler(log_file_handler)

    return out_sam_file


# Adds arguments for the argument parser
def add_args(parser, required_args):
    required_args.add_argument("--genome_index", "-g",
                               dest="genome_index",
                               required=True,
                               help="Genome index directory to be used by aligner")
    required_args.add_argument("--input", "-i",
                               dest="input_files",
                               nargs="+",
                               required=True,
                               help="/path/to/read1 [/path/to/read2] (e.g. a1.fq,b1.fq a2.fq,b2.fq)")
    required_args.add_argument("--aligner_tool", "-at",
                               dest="aligner",
                               required=True,
                               type=aligner_str,
                               help="Aligner to be used (STAR|Subread)")
    parser.add_argument("--aligner_extra_args", "-ae",
                        dest="aligner_extra_args",
                        default="",
                        nargs="?",
                        help="Extra argument to be passed to aligner")
    parser.add_argument("--output_dir", "-o",
                        dest="output_dir",
                        default=".",
                        nargs="?",
                        type=output_dir_str,
                        help="Output directory (default: current directory)")
    parser.add_argument("--output_prefix", "-p",
                        dest="prefix",
                        help="Prefix for all the output files (Default: uses input read file name)")
    parser.add_argument("--bam",
                        action="store_true",
                        dest="bam_output",
                        help="BAM output file format (Default: SAM output file format)")
    parser.add_argument("--clean",
                        action="store_true",
                        dest="clean_files",
                        help="Keep alignment file but remove other files produced by aligner (Default: Keep all files)")
    parser.add_argument("--quiet", "-q",
                        action="store_true",
                        dest="quiet",
                        help=argparse.SUPPRESS)
    parser.add_argument("--threads", "-t",
                        dest="num_threads",
                        default=4,
                        type=int,
                        help="Number of threads to be used by aligner or counter if supported (Default: %(default)s)")


# Checks for valid aligner
def aligner_str(s):
    s = s.lower()
    if not re.match("star|subread", s):
        error = "Supported aligners (STAR|Subread)"
        raise argparse.ArgumentTypeError(error)
    else:
        return s


# Strip slash from output directory
def output_dir_str(s):
    return s.rstrip("/")


# Checks for tools execution
def check_tools(aligner):
    aligner_execs = {"star": "STAR", "subread": "subread-align"}
    try:
        align = Popen(shlex.split(aligner_execs[aligner]), stdout=PIPE, stderr=PIPE)
        align.communicate()
    except:
        error = "[%s] Error encountered when being called. Script will not run" % aligner_execs[aligner]
        raise RuntimeError(error)


# Runs STAR
def run_star(genome_index, input_files, output_prefix, num_threads, aligner_extra_args, is_bam, is_clean_files,
             root_logger, is_quiet):
    if is_bam:
        output_file = "%s.Aligned.out.bam" % output_prefix
    else:
        output_file = "%s.Aligned.out.sam" % output_prefix

    command = "STAR --runThreadN {threads} {aligner_extra_args} " \
              "--genomeDir {genome_index} --readFilesIn {read_files} " \
              "--outFileNamePrefix {output_prefix}. {gz_option} {bam_option} " \
              "--outSAMunmapped Within KeepPairs". \
        format(threads=num_threads,
               aligner_extra_args=aligner_extra_args,
               genome_index=genome_index,
               read_files=" ".join(input_files),
               output_prefix=output_prefix,
               gz_option="--readFilesCommand zcat" if input_files[0].split(",")[0].endswith("gz") else "",
               bam_option="--outSAMtype BAM Unsorted" if is_bam else "")

    run_tool("STAR", command, output_file, root_logger, is_quiet)

    if is_clean_files:
        os.remove("%s.Log.final.out" % output_prefix)
        os.remove("%s.Log.out" % output_prefix)
        os.remove("%s.Log.progress.out" % output_prefix)
        os.remove("%s.SJ.out.tab" % output_prefix)

    return output_file


# Runs Subread
def run_subread(genome_index, input_files, output_prefix, num_threads, aligner_extra_args, is_bam, root_logger,
                is_quiet):
    if len(input_files) == 2:
        read_files = "-r %s -R %s" % (input_files[0], input_files[1])
    else:
        read_files = "-r %s" % " ".join(input_files)

    if is_bam:
        output_file = "%s.bam" % output_prefix
    else:
        output_file = "%s.sam" % output_prefix

    command = "subread-align -T {threads} -t 0 {aligner_extra_args} -i " \
              "{genome_index} {read_files} -o {output_file} {bam_option}". \
        format(threads=num_threads,
               aligner_extra_args=aligner_extra_args,
               genome_index=genome_index,
               read_files=read_files,
               output_file=output_file,
               bam_option="" if is_bam else "--SAMoutput")

    run_tool("Subread", command, output_file, root_logger, is_quiet)

    return output_file


# Runs tools with the given command
# Also checks for the existence of one of the expected output from the tools
def run_tool(tool, command, output_file, root_logger, is_quiet):
    if not is_quiet:
        root_logger.info("Command: %s" % command)

    tool_process = Popen(shlex.split(command), stdout=PIPE, stderr=PIPE)
    tool_out, tool_err = tool_process.communicate()

    if tool_process.returncode != 0:
        error = "{tool} failed to complete (non-zero return code)!\n" \
                "{tool} stdout: {out}\n{tool} stderr: {err}\n". \
            format(tool=tool,
                   out=tool_out.decode("utf8") if tool.lower() != "bwa" else "",
                   err=tool_err.decode("utf8"))
        raise RuntimeError(error)
    elif not os.path.exists(output_file):
        error = "{tool} failed to complete (no output file is found)!\n" \
                "{tool} stdout: {out}\n{tool} stderr: {err}\n". \
            format(tool=tool,
                   out=tool_out.decode("utf8") if tool.lower() != "bwa" else "",
                   err=tool_err.decode("utf8"))
        raise RuntimeError(error)
    elif "[Errno" in tool_err.decode("utf8").strip():
        error = "{tool} failed to complete (error)!\n" \
                "{tool} stdout: {out}\n{tool} stderr: {err}\n". \
            format(tool=tool,
                   out=tool_out.decode("utf8") if tool.lower() != "bwa" else "",
                   err=tool_err.decode("utf8"))
        raise RuntimeError(error)


if __name__ == "__main__":
    main()

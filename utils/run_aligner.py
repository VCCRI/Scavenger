#!/usr/bin/python3

import argparse
import logging
import os
import re
import shlex
import sys
from subprocess import Popen, PIPE


# Main function
def run_aligner(parser_result):
    aligner = parser_result.aligner.lower()
    global quiet
    quiet = parser_result.quiet

    # Checks for valid number of inputs
    if len(parser_result.input) > 2:
        error = "Invalid input, input takes at most 2 arguments.\n" \
                "Example: --input/-i /path/to/read1 [/path/to/read2] " \
                "(e.g. a1.fq,b1.fq a2.fq,b2.fq)\n" \
                "Your input: %s" % " ".join(parser_result.input)
        raise argparse.ArgumentTypeError(error)

    # Checks for number of each paired end input is the same
    elif (len(parser_result.input) == 2 and
                  len(parser_result.input[0].split(",")) != len(parser_result.input[1].split(","))):
        error = "Invalid input, the number of read1 does not equal to that of read2\n" \
                "You input: %s" % " ".join(parser_result.input)
        raise argparse.ArgumentTypeError(error)

    check_tools(aligner)

    if not quiet:
        log_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt='%Y-%m-%d %I:%M:%S %p')
        global root_logger
        root_logger = logging.getLogger()
        root_logger.setLevel("INFO")

    if parser_result.prefix is None:
        prefix = os.path.splitext(os.path.basename(parser_result.input[0].split(",")[0]))[0].\
            rstrip(".fastq").rstrip(".fq")
    else:
        prefix = parser_result.prefix

    if parser_result.output_dir is None:
        output_prefix = prefix

        if not quiet:
            log_file_handler = logging.FileHandler("%s_aligner.log" % prefix)
    else:
        output_prefix = "%s/%s" % (parser_result.output_dir.rstrip("/"), prefix)

        try:
            os.mkdir(parser_result.output_dir)
        except FileExistsError:
            pass

        if not quiet:
            log_file_handler = logging.FileHandler("%s/%s_aligner.log" % (parser_result.output_dir.rstrip("/"), prefix))

    if not quiet:
        log_file_handler.setFormatter(log_formatter)
        root_logger.addHandler(log_file_handler)

    if not quiet and len(root_logger.handlers) == 1:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(log_formatter)
        root_logger.addHandler(console_handler)

    tools_names = {"star": "STAR", "subread": "Subread"}

    if not quiet:
        root_logger.info("Aligning reads using %s..." % tools_names[aligner])

    if aligner == "star":
        out_sam_file = run_star(parser_result, output_prefix)
    elif aligner == "subread":
        out_sam_file = run_subread(parser_result, output_prefix)
    else:
        out_sam_file = None

    if not quiet:
        root_logger.info("Completed reads alignment")
        root_logger.removeHandler(log_file_handler)

    return out_sam_file


# Adds arguments for the argument parser
def add_args(parser, required_args):
    required_args.add_argument("--input", "-i",
                               dest="input",
                               nargs="+",
                               required=True,
                               help="/path/to/read1 [/path/to/read2] (e.g. a1.fq,b1.fq a2.fq,b2.fq)")
    required_args.add_argument("--aligner_tool", "-at",
                               dest="aligner",
                               required=True,
                               type=aligner_string,
                               help="Aligner to be used (STAR|Subread)")
    parser.add_argument("--aligner_extra_args", "-ae",
                        dest="aligner_extra_args",
                        default="",
                        nargs="?",
                        help="Extra argument to be passed to aligner")
    parser.add_argument("--output_dir", "-o",
                        dest="output_dir",
                        nargs="?",
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
                        dest="threads",
                        default=4,
                        type=int,
                        help="Number of threads to be used by aligner or counter if supported (Default: %(default)s)")


# Checks for valid aligner
def aligner_string(s):
    s = s.lower()
    if not re.match("star|subread", s):
        error = "Supported aligners (STAR|Subread)"
        raise argparse.ArgumentTypeError(error)
    else:
        return s


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
def run_star(parser_result, output_prefix):
    if parser_result.bam_output:
        output_file = "%s.Aligned.out.bam" % output_prefix
    else:
        output_file = "%s.Aligned.out.sam" % output_prefix

    command = "STAR --runThreadN {threads} {aligner_extra_args} " \
              "--genomeDir {genome_index} --readFilesIn {read_files} " \
              "--outFileNamePrefix {output_prefix}\. {gz_option} {bam_option} " \
              "--outSAMunmapped Within KeepPairs". \
        format(threads=parser_result.threads,
               aligner_extra_args=parser_result.aligner_extra_args,
               genome_index=parser_result.genome_index,
               read_files=" ".join(parser_result.input),
               output_prefix=output_prefix,
               gz_option="--readFilesCommand zcat" if parser_result.input[0].split(",")[0].endswith("gz") else "",
               bam_option="--outSAMtype BAM Unsorted" if parser_result.bam_output else "")

    run_tool("STAR", command, output_file)

    if parser_result.clean_files:
        os.remove("%s.Log.final.out" % output_prefix)
        os.remove("%s.Log.out" % output_prefix)
        os.remove("%s.Log.progress.out" % output_prefix)
        os.remove("%s.SJ.out.tab" % output_prefix)

    return output_file


# Runs Subread
def run_subread(parser_result, output_prefix):
    if len(parser_result.input) == 2:
        read_files = "-r %s -R %s" % (parser_result.input[0], parser_result.input[1])
    else:
        read_files = "-r %s" % " ".join(parser_result.input)

    if parser_result.bam_output:
        output_file = "%s.bam" % output_prefix
    else:
        output_file = "%s.sam" % output_prefix

    command = "subread-align -T {threads} -t 0 {aligner_extra_args} -i " \
              "{genome_index} {read_files} -o {output_file} {bam_option}". \
        format(threads=parser_result.threads,
               aligner_extra_args=parser_result.aligner_extra_args,
               genome_index=parser_result.genome_index,
               read_files=read_files,
               output_file=output_file,
               bam_option="" if parser_result.bam_output else "--SAMoutput")

    run_tool("Subread", command, output_file)

    return output_file

# Runs tools with the given command
# Also checks for the existence of one of the expected output from the tools
def run_tool(tool, command, output_file):
    if not quiet:
        root_logger.info("Command: %s" % command)

    tool_process = Popen(shlex.split(command), stdout=PIPE, stderr=PIPE)
    tool_out, tool_err = tool_process.communicate()

    if tool_process.returncode != 0:
        error = "{tool} failed to complete (non-zero return code)!\n" \
                "{tool} stdout: {out}\n{tool} stderr: {err}\n". \
            format(tool=tool,
                   out=tool_out.decode("utf8"),
                   err=tool_err.decode("utf8"))
        raise RuntimeError(error)
    elif not os.path.exists(output_file):
        error = "{tool} failed to complete (no output file is found)!\n" \
                "{tool} stdout: {out}\n{tool} stderr: {err}\n". \
            format(tool=tool,
                   out=tool_out.decode("utf8"),
                   err=tool_err.decode("utf8"))
        raise RuntimeError(error)
    elif "[Errno" in tool_err.decode("utf8").strip():
        error = "{tool} failed to complete (error)!\n" \
                "{tool} stdout: {out}\n{tool} stderr: {err}\n". \
            format(tool=tool,
                   out=tool_out.decode("utf8"),
                   err=tool_err.decode("utf8"))
        raise RuntimeError(error)


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="RNA-Seq Aligner")
    required_arguments = arg_parser.add_argument_group('required arguments')
    required_arguments.add_argument("--genome_index", "-g",
                                    dest="genome_index",
                                    required=True,
                                    help="Genome index directory to be used by aligner")
    add_args(arg_parser, required_arguments)

    run_aligner(arg_parser.parse_args())

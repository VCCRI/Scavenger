import argparse
import logging
import os
import re
import shlex
import sys
from subprocess import Popen, PIPE


def main():
    parser = argparse.ArgumentParser(description="Aligner Index Builder")
    required_args = parser.add_argument_group('required arguments')
    add_args(parser, required_args)
    parser.set_defaults(method=build_index)

    parser_result = parser.parse_args()
    parser_result.method(**vars(parser_result))


# Main function
def build_index(aligner, genome_files, output_dir, prefix, num_threads, builder_extra_args, quiet, annotation=None,
                **kwargs):
    check_tools(aligner)

    # Set prefix from first input file
    if prefix is None:
        prefix = os.path.splitext(os.path.basename(genome_files.split(",")[0]))[0].rstrip(".fasta").rstrip(".fa")

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
        log_file_handler = logging.FileHandler("{}/{}_index_build.log".format(output_dir, prefix))
        log_file_handler.setFormatter(log_formatter)
        root_logger.addHandler(log_file_handler)

        # Setup stdout logger
        if len(root_logger.handlers) == 1:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(log_formatter)
            root_logger.addHandler(console_handler)

        tools_names = {"star": "STAR", "subread": "Subread"}
        root_logger.info("Building index for %s..." % tools_names[aligner])

    output_prefix = "{}/{}".format(output_dir, prefix)
    if aligner == "star":
        genome_index = build_star(genome_files, output_prefix, num_threads, builder_extra_args, annotation,
                                  root_logger, quiet)
    elif aligner == "subread":
        genome_index = build_subread(genome_files, output_prefix, builder_extra_args, root_logger, quiet)
    else:
        genome_index = None

    if not quiet:
        root_logger.info("Completed building index")
        root_logger.removeHandler(log_file_handler)

    return genome_index


# Adds all the arguments to the argument parser
def add_args(parser, required_args):
    required_args.add_argument("--genome_files", "-G",
                               dest="genome_files",
                               required=True,
                               help="FASTA Genome file (Note: Bismark takes the directory containing the FASTA file instead)")
    required_args.add_argument("--aligner_tool", "-at",
                               dest="aligner",
                               required=True,
                               type=aligner_string,
                               help="Aligner to build index (STAR|Subread)")
    parser.add_argument("--builder_extra_args", "-be",
                        dest="builder_extra_args",
                        default="",
                        nargs="?",
                        help="Extra argument to be passed to aligner index build")
    parser.add_argument("--annotation", "-a",
                        dest="annotation",
                        help="Annotation file to be used")
    parser.add_argument("--output_dir", "-o",
                        dest="output_dir",
                        default=".",
                        nargs="?",
                        type=output_dir_str,
                        help="Output directory (default: current directory)")
    parser.add_argument("--output_prefix", "-p",
                        dest="prefix",
                        help="Prefix for all the output files (default: uses input read file name)")
    parser.add_argument("--quiet", "-q",
                        action="store_true",
                        dest="quiet",
                        help=argparse.SUPPRESS)
    parser.add_argument("--threads", "-t",
                        dest="num_threads",
                        default=4,
                        type=int,
                        help="Number of threads to be used by aligner index builder (default: %(default)s)")


# Checks for valid aligner
def aligner_string(s):
    s = s.lower()
    regex = "star|subread"

    if not re.match(regex, s):
        error = "Aligner to be used (STAR|Subread)"
        raise argparse.ArgumentTypeError(error)
    else:
        return s


# Strip slash from output directory
def output_dir_str(s):
    return s.rstrip("/")


# Checks for tools execution
def check_tools(aligner):
    tools_dir = {"star": "STAR", "subread": "subread-buildindex"}
    try:
        build = Popen(shlex.split(tools_dir[aligner]), stdout=PIPE, stderr=PIPE)
        build.communicate()
    except:
        error = "[%s] Error encountered when being called. Script will not run." % tools_dir[aligner]
        raise RuntimeError(error)


# Builds STAR index
def build_star(genome_files, output_prefix, num_threads, builder_extra_args, annotation_file, root_logger, quiet):
    genome_index = "%s_star" % output_prefix
    os.mkdir(genome_index) if not os.path.exists(genome_index) else 0
    output_file = "%s/Genome" % genome_index

    command = "STAR --runThreadN {threads} --runMode genomeGenerate " \
              "--genomeDir {genome_index} " \
              "--genomeFastaFiles {genome_file} {annotation_option} " \
              "{builder_extra_args}". \
        format(threads=num_threads,
               genome_index=genome_index,
               genome_file=genome_files,
               annotation_option="--sjdbGTFfile {}".format(annotation_file) if annotation_file else "",
               builder_extra_args=builder_extra_args)

    run_tool("STAR", command, output_file, root_logger, quiet)

    return genome_index


# Builds Subread index
def build_subread(genome_files, output_prefix, builder_extra_args, root_logger, quiet):
    genome_index = "%s_subread/" % output_prefix
    os.mkdir(genome_index) if not os.path.exists(genome_index) else 0
    genome_index += "genome"
    output_file = "%s.00.b.tab" % genome_index

    command = "subread-buildindex -o {genome_index} " \
              "{builder_extra_args} {genome_file}". \
        format(genome_index=genome_index,
               builder_extra_args=builder_extra_args,
               genome_file=genome_files)

    run_tool("Subread-Build", command, output_file, root_logger, quiet)

    return genome_index


# Runs tools with the given command
# Also checks for the existence of one of the expected output from the tools
def run_tool(tool, command, output_file, root_logger, quiet):
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
    main()

# Scavenger

Rescue potential false negative unmapped reads in alignment tools

Manuscript available now on **bioRxiv**: https://www.biorxiv.org/content/early/2018/06/13/345876

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and
testing purposes.

### Prerequisites

Python3 is required with the following libraries:

* [Biopython](https://github.com/biopython/biopython)
* [intervaltree](https://github.com/chaimleib/intervaltree)
* [Pysam](https://github.com/pysam-developers/pysam)

These are included in `requirements.txt`, run the following commands to install them:

```
pip install -r requirements.txt
```

Type the following command to install these libraries

```
pip3 install --upgrade biopython pysam intervaltree
```

The alignment tool that you will be using is also required. Currently, it supports the following aligners:

* STAR
* Subread

Please make sure that the aligner that you are using is in your path. Please note that BLASTN is also required for rescuing so make sure blastn is in your path.

## Running scavenger.py

Rescue unmapped reads. When running the script, you can specify a pre-built aligner's index. If you do not specify it, the script will first build the index automatically with the given FASTA file.

The script will produce a new sam file called `<prefix>_rescued.sam` and some counting information.

### Usage

```
python3 usage: scavenger.py [options] -G/--genome_file <genome_file> -i/--input <input> -at/--aligner_tool <aligner>
```

#### Required Arguments

| Option                             | Argument |
| ---------------------------------- | -------- |
| `-g/--genome_index <genome_index>` | The pre-built genome index for the aligner |
| `-i/--input <input>`               | A comma separated list of input reads (Example: readA.fq,readB.fq). If the reads are paired, use a space to separate reads 1 and 2 (Example: readA_1.fq,readB_1.fq readA_2.fq,readB_2.fq) |
| `-at/--aligner_tool <aligner>`     | The alignment tool to perform alignment |

#### Optional Arguments

| Option                                  | Argument |
| --------------------------------------- | -------- |
| `-ae/--aligner_extra_args <extra_args>` | Extra arguments for the aligner. Use this option with quotes (Example: `"-ae=<extra_args>"`) |
| `-be/--builder_extra_args <extra_args>` | Extra arguments for the aligner index building. Use this option with quotes (Example: `"-be=<extra_args>"`) |
| `--blast_perc_identity`                 | Minimum percentage of identity for BLASTN |
| `--blast_perc_query_coverage`           | Minimum percentage of query coverage for BLASTN |
| `-g/--genome_index <genome_index>`      | The directory of the aligner's index. For Bowtie2, BWA, you will have to specify the prefix of the index files as well |
| `-o/--output_dir <output_dir>`          | The output directory for the index (Default: current directory) |
| `-p/--output_prefix <prefix>`           | The prefix for the output index folder (Default: uses the first input file as the prefix) |
| `-t/--threads`                          | The number of threads to be used by the index builder (Default: 4) |

### Example Usage

For rescuing reads using STAR

```
python3 scavenger.py -G genome.fa -i readA.fq -at star -t 8
```

## Running build_aligner_index.py

Creates the index for a specified aligner

### Usage

```
python3 utils/build_aligner_index.py [options] -G/--genome_file <genome_file> -at/--aligner_tool <aligner>
```

#### Required Arguments

| Option                           | Argument                                  |
| -------------------------------- | ----------------------------------------- |
| `-G/--genome_file <genome_file>` | The reference genome file in FASTA format |
| `-at/--aligner_tool <aligner>`   | The alignment tool to build index for     |

#### Optional Arguments

| Option                                  | Argument |
| --------------------------------------- | -------- |
| `-be/--builder_extra_args <extra_args>` | Extra arguments for the aligner index building. Use this option with quotes (Example: `"-be=<extra_args>"`) |
| `-a/--annotation <annotation>`          | The annotation file in GTF/GFF format |
| `-o/--output_dir <output_dir>`          | The output directory for the index (Default: current directory) |
| `-p/--output_prefix <prefix>`           | The prefix for the output index folder (Default: uses genome file as the prefix) |
| `-s/--silent`                           | Set to silent the logging information (Default: False) |
| `-t/--threads`                          | The number of threads to be used by the index builder (Default: 4) |

### Example Usage

```
python3 utils/build_aligner_index.py -G genome.fa -at star -t 8
```

## Running run_aligner.py

Runs a specific aligner

### Usage

```
python3 utils/run_aligner.py [options] -i/--input <input> -g/--genome_index <genome_index> -at/--aligner_tool <aligner>
```

#### Required Arguments

| Option                             | Argument |
| ---------------------------------- | -------- |
| `-i/--input <input>`               | A comman separated list of input reads (Example: readA.fq,readB.fq). If the reads are paired, use a space to separate reads 1 and 2 (Example: readA_1.fq,readB_1.fq readA_2.fq,readB_2.fq) |
| `-g/--genome_index <genome_index>` | The directory of the aligner's index |
| `-at/--aligner_tool <aligner>`     | The alignment tool to perform alignment |

#### Optional Arguments

| Option                                  | Argument |
| --------------------------------------- | -------- |
| `-ae/--aligner_extra_args <extra_args>` | Extra arguments for the aligner. Use this option with quotes (Example: `"-ae=<extra_args>"`) |
| `-o/--output_dir <output_dir>`          | The output directory for the index (Default: current directory) |
| `-p/--output_prefix <prefix>`           | The prefix for the output index folder (Default: uses the first input file as the prefix) |
| `-s/--silent`                           | Set to silent the logging information (Default: False) |
| `-t/--threads`                          | The number of threads to be used by the index builder (Default: 4) |

### Example Usage

For a single single-end file using STAR

```
python3 utils/run_aligner.py -i readA.fq -g star_index/ -at star -t 8
```

For a single single-end files using Subread

```
python3 utils/run_aligner.py -i readA.fq,readB.fq -g subread_index/ -at subread -t 8
```

#!/bin/bash
###############################################################################
# designed for use with aws instance with ssd (called from --user-data option #
# mounts ssd to /ssd & creates directories for DNA variant calling pipeline   #
#                                                                             #
# This is really suited specifically for r3 instances - where the ephemeral   #
# drives are not configured.  Another assumption is that the drives are       #
# "mapped" at launch time, like: --block-device-mapping "/dev/sdb=ephemeral0" #
# atm - targeting r3.8xlarge - with 2 x 320g drives                           #
###############################################################################

genome_dir=genome_ref
star_dir=star_ref
hisat_dir=hisat_ref
bowtie2_dir=bowtie2_ref
s3_genome_ref=s3://vccri.ho-lab.feat-quant/genomes/mm10_Dec2016/genome_ref
s3_star_ref=s3://vccri.ho-lab.feat-quant/genomes/mm10_Dec2016/star_index
#s3_hisat_ref=s3://vccri.ho-lab.feat-quant/hisat_refs/hg38
#s3_bowtie2_ref=s3://vccri.ho-lab.feat-quant/genomes/hg38/bowtie2_index
#s3_genome_ref=s3://vccri.ho-lab.feat-quant/genome_refs/mm10_gencode
#s3_star_ref=s3://vccri.ho-lab.feat-quant/star_refs/mm10_gencode_sparse
s3_software_install=s3://vccri.ho-lab.feat-quant/software_install
aws_region=us-west-2
failure_file=/mnt2/app/BOOTSTRAP_FAILURE

#colours; need to use -e option with echo
red='\e[0;31m'
cyan='\e[0;36m'
green='\e[0;32m'
yellow='\e[1;33m'
purple='\e[0;35m'
nc='\e[0m' #no colour

#program usage
usage() {
    echo -e "${red}program exited due to invalid usage${nc}"
    echo -e "${yellow}usage:${purple} $0 ${cyan}<parm 1>${nc}"
    exit 1
}

#checks latest return status
#accepts one argument - name of program call
check_status() {
    if [ $? -ne 0 ] ; then
        echo -e "${red}<${0}> program exited due to unsuccessful excecution: ${cyan}${1}${nc}"
        exit 1
    fi
}

#function to exit program with message
exit_msg() {
    echo -e "${red}<${0}> exiting program: ${cyan}${1}${nc}"
    exit 1
}

create_dir() {
    dir=$1
    # allow for case where image already has dir
    sudo mkdir -p $dir
    check_status "mkdir -p $dir"
    sudo chmod g+rwx $dir
    check_status "chmod $dir"
    sudo chgrp ec2-user $dir
    check_status "chgrp $dir"
    sudo chown ec2-user $dir
    check_status "chown $dir"
}


mount_drive() {
    mountdir=$1
    dev=$2
    #create directory onto which the drive will be mapped
    mkdir -p $mountdir
    check_status "mkdir -p $mountdir"
    #put file system on drive
    mkfs.ext4 -E nodiscard -F $dev
    check_status "mkfs"
    #mount the drive
    mount -o discard $dev $mountdir
    check_status "mount"
    echo -e "${yellow}STATUS: ${green}SSD successfully mounted${nc}"
}

echo "***************"
echo -e "${yellow}START${nc}"
date
echo "***************"
umount /media/ephemeral0

mount_dir=/mnt1
device=/dev/xvdb
echo -e "${yellow}STATUS: ${cyan}Begin SSD mount process for $mount_dir on device $device...${nc}"
mount_drive $mount_dir $device

mount_dir=/mnt2
device=/dev/xvdc
echo -e "${yellow}STATUS: ${cyan}Begin SSD mount process for $mount_dir on device $device...${nc}"
mount_drive $mount_dir $device

#copy data to newly mounted drive
mount_dir=/mnt1
create_dir $mount_dir/data
mount_dir=/mnt2
create_dir $mount_dir/app
create_dir $mount_dir/app/work
create_dir $mount_dir/app/data
create_dir $mount_dir/app/data/analysis
create_dir $mount_dir/ref
create_dir $mount_dir/output
create_dir $mount_dir/working

# create bin directory for /home/ec2-user
home_bin_dir=/home/ec2-user/bin
create_dir $home_bin_dir

set -e
set -o pipefail

function unzip_files() {
    # unzip any .gz files in current directory or any subdirectories
    # determine if there are any .gz files; note that without this test, the xargs command would fail with a null input
    zip_files=$( find -L . -name "*.gz" -print0 )
    if [ "$zip_files" != "" ] ; then
        # unzip all the .gz files using as many processors as possible
        find -L . -name "*.gz" -print0 | xargs -P0 -0 gunzip
    fi
}


# copy reference files
pushd /mnt2/ref > /dev/null

echo "***************"
echo -e "${yellow}GENOME REF${nc}"
echo "***************"
# Genome Ref
aws s3 sync $s3_genome_ref $genome_dir --region=$aws_region
pushd $genome_dir > /dev/null
unzip_files
popd > /dev/null

echo "***************"
echo -e "${yellow}STAR REF${nc}"
date
echo "***************"
# STAR Ref
aws s3 sync $s3_star_ref $star_dir --region=$aws_region
pushd $genome_dir > /dev/null
unzip_files
popd > /dev/null

popd > /dev/null

pushd /mnt2/app > /dev/null

echo "***************"
echo -e "${yellow}COPY INSTALL SOFTWARE${nc}"
date
echo "***************"
# copy install software
aws s3 cp $s3_software_install . --recursive --region=$aws_region

# give rights to ec2-user
for f in * ; do
    sudo chgrp ec2-user $f
    sudo chown ec2-user $f
done


echo "***************"
echo -e "${yellow}INSTALL STAR${nc}"
date
echo "***************"
# STAR
tar -xzf STAR*.tar.gz
star_path=$( find . -name "STAR"|grep -E "/Linux_x86_64/" )
# symbolic link to the STAR directory (rather than to the executable itself)
ln -s ${star_path%STAR} STAR

echo "***************"
echo -e "${yellow}INSTALL SUBREAD${nc}"
date
echo "***************"
# Install subread (featureCount)
tar -xzf subread*.tar.gz
fc=$( find -name "featureCounts"|grep bin )
sr_path=${fc%featureCounts}
ln -s $sr_path subread

echo "***************"
echo -e "${yellow}INSTALL SAMTOOLS${nc}"
date
echo "***************"
# Install samtools
tar -xjf samtools*.tar.bz2
sam_dir=$( find . -maxdepth 1 -type d -name "samtools*" )
pushd $sam_dir > /dev/null
make
sudo make install
popd > /dev/null

echo "***************"
echo -e "${yellow}INSTALL BOWTIE${nc}"
date
echo "***************"
# Install Bowtie2 (system wide install from source)
unzip bowtie*source.zip
bowtie_dir=$( find . -maxdepth 1 -type d -name "bowtie*")
pushd $bowtie_dir > /dev/null
make
sudo make install
popd > /dev/null

echo "***************"
echo -e "${yellow}INSTALL TOPHAT${nc}"
date
echo "***************"
# Install TopHat2
tar -xzf tophat*.tar.gz
tophat_dir=$( find . -maxdepth 1 -type d -name "tophat*")
ln -s $tophat_dir tophat

echo "***************"
echo -e "${yellow}INSTALL HTSLIB${nc}"
date
echo "***************"
# Install htslib
hts_dir=$( find $sam_dir -maxdepth 1 -type d -name "htslib-*" )
pushd $hts_dir > /dev/null
make
sudo make install
popd > /dev/null

echo "***************"
echo -e "${yellow}INSTALL PICARD TOOLS ${nc}"
date
echo "***************"
# Install picard_tools
unzip picard-tools*.zip
pic_jar=$( find . -name picard.jar )
pic_path=${pic_jar%picard.jar}
ln -s $pic_path picard-tools

echo "***************"
echo -e "${yellow}INSTALL TRIM GALORE${nc}"
date
echo "***************"
# trim galore
tg=trim_galore
unzip trim_galore*.zip
tg_path=$( find . -name $tg )
ln -s $tg_path $tg

echo "***************"
echo -e "${yellow}TRIMMOMATIC${nc}"
date
echo "***************"
# trimmomatic
unzip Trimmomatic*.zip
tm=$( find . -name trimmomatic*.jar )
ln -s $tm ${tm##*/}
# hardcoded - TODO make version agnostic
ln -s Trimmomatic-0.36/adapters/NexteraPE-PE.fa NexteraPE-PE.fa

echo "***************"
echo -e "${yellow}PRINSEQ${nc}"
date
echo "***************"
# prinseq
ps=prinseq-lite.pl
tar -xzf prinseq-lite*.tar.gz
ps_path=$( find . -name "$ps" )
ln -s $ps_path $ps

echo "***************"
echo -e "${yellow}HISAT2${nc}"
date
echo "***************"
# HISAT2
# version agnostic
for f in hisat2-*-Linux_x86_64.zip ; do
    if ! [ -f "$f" ] ; then
        echo "ERROR with HISAT2 installation - zip file" >&2
        break
    fi
    unzip $f
    for d in hisat2*/ ; do
        if ! [ -d "$d" ] ; then
            echo "ERROR with HISAT2 installation - HISAT directory" >&2
            break
        fi
        hisat_dir=$d
        pushd "$hisat_dir"
        # don't need to make - as we are using binaries
        #make
        # put copy in dir that is included in path
        cp hisat2* *.py $home_bin_dir
        popd
        break
    done
    break
done

echo "***************"
echo -e "${yellow}STRINGTIE${nc}"
date
echo "***************"
# stringtie
completed=false
for f in stringtie*.tar.gz ; do
    if ! [ -f "$f" ] ; then
        echo "ERROR with stringtie installation - zip file" >> $failure_file
        break
    fi
    tar -xzf $f
    for d in stringtie*/ ; do
        if ! [ -d "$d" ] ; then
            echo "ERROR with stringtie installation - stringtie directory" >> $failure_file
            break
        fi
        stringtie_dir=$d
        # don't need to make - as we are using binaries
        # put copy in dir that is included in path
        chmod +x $stringtie_dir/stringtie
        cp $stringtie_dir/stringtie $home_bin_dir
        [ $? -eq 0 ] && completed=true
        break
    done
    break
done
if ! $completed ; then
    echo "unable to install stringtie" >> $failure_file
fi

echo "***************"
echo -e "${yellow}PREPDE${nc}"
date
echo "***************"
# prepDE.py
f=prepDE.py
if [ -f $f ] ; then
    chmod +x $f
    # put copy in dir that is included in path
    cp $f $home_bin_dir
else
    echo "prepDE.py - could not find file" >> $failure_file
fi

# Install blast

echo "***************"
echo -e "${yellow}BLAST${nc}"
date
echo "***************"
blast=$( find . -name ncbi-blast*.rpm )
sudo yum install -y $blast

# -------------------------------------------------------------
# no longer in /mnt/app
popd > /dev/null

echo "***************"
echo -e "${yellow}YUM UPDATE${nc}"
date
echo "***************"
sudo yum update -y --skip-broken
echo "***************"
echo -e "${yellow}UPGRADE PIP${nc}"
date
echo "***************"
sudo pip install --upgrade pip
echo "***************"
echo -e "${yellow}INSTALL AWSCLI${nc}"
date
echo "***************"
sudo python -m pip install awscli --upgrade
echo "***************"
echo -e "${yellow}JAVA${nc}"
date
echo "***************"

# Install java8
sudo yum install java-1.8.0-openjdk.x86_64 -y

# Install HTSeq
echo "***************"
echo -e "${yellow}PYSAM${nc}"
date
echo "***************"
sudo python -m pip install pysam
echo "***************"
echo -e "${yellow}HTSEQ${nc}"
date
echo "***************"
sudo python -m pip install htseq

echo "***************"
echo -e "${yellow}PYSAM 3${nc}"
date
echo "***************"
sudo python3 -m pip install pysam
echo "***************"
echo -e "${yellow}BIOPYTHON${nc}"
date
echo "***************"
sudo python3 -m pip install biopython
echo "***************"
echo -e "${yellow}INTERVALTREE${nc}"
date
echo "***************"
sudo python3 -m pip install intervaltree

echo "***************"
echo -e "${yellow}GIT${nc}"
date
echo "***************"
# Install git
sudo yum -y install git

echo "***************"
echo -e "${yellow}FINISH${nc}"
date
echo "***************"
# STAR
sudo ln -s /mnt2/app/STAR/STAR /usr/local/bin/STAR

# success
touch /mnt2/app/BOOTSTRAP_SUCCESS

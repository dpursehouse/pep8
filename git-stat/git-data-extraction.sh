#!/bin/bash
################################################################################
# This script collects the number of commits, insertions, deletions, 
# files changed between two timestamps (from old manifest to new manifest)
################################################################################
if [ -z $WORKSPACE ]; then
    WORKSPACE=$PWD
fi

USAGE="Usage :`basename $0 ` <previous manifest>  <current manifest>"

PREV_MANIFEST=$1
CUR_MANIFEST=$2

if [ -z $PREV_MANIFEST ]; then
    echo $USAGE >&2
    exit 3
fi

if [ -z $CUR_MANIFEST ]; then
    CUR_MANIFEST=$PREV_MANIFEST
    PREV_MANIFEST=
fi

LOGDIR=$WORKSPACE/logdir

if [ ! -d $LOGDIR ]; then
    mkdir $LOGDIR
fi

SCRIPT='
BEGIN {
	companies["amd.com"] = "AMD";
	companies["android.com"] = "Google";
	companies["atheros.com"] = "Atheros";
	companies["axis.com"] = "Axis";
	companies["broadcom.com"] = "Broadcom";
	companies["cisco.com"] = "Cisco";
	companies["codeaurora.org"] = "QualComm";
	companies["columbia.edu"] = "Columbia Univ";
	companies["corpusers.net"] = "Sony Ericsson";
	companies["dodologics.com"] = "Dodo Logics";
	companies["garmin.com"] = "Garmin";
	companies["gnome.org"] = "Gnome.org";
	companies["google.com"] = "Google";
	companies["hitachi.com"] = "Hitachi";
	companies["holtmann.org"] = "Holtmann";
	companies["htc.com"] = "HTC";
	companies["ibm.com"] = "IBM";
	companies["intel.com"] = "Intel";
	companies["kernel.org"] = "Kernel.org";
	companies["marvell.com"] = "Marvell";
	companies["motorola.com"] = "Motorola";
	companies["nokia.com"] = "Nokia";
	companies["nxp.com"] = "NXP";
	companies["oracle.com"] = "Oracle";
	companies["qualcomm.com"] = "QualComm";
	companies["quicinc.com"] = "QualComm";
	companies["redhat.com"] = "RedHat";
	companies["renesas.com"] = "Renesas";
	companies["samba.org"] = "Samba.org";
	companies["samsung.com"] = "Samsung";
	companies["sgi.com"] = "SGI";
	companies["sonyericsson.com"] = "Sony Ericsson";
	companies["stericsson.com"] = "ST Ericsson";
	companies["suse.cz"] = "Suse";
	companies["suse.de"] = "Suse";
	companies["tactel.se"] = "Tactel";
	companies["trusted-logic.com"] = "Trusted Logic";
}

/.+@.+/ {
	company = "Unkown";
	for (i in companies) {
		if (index($1, i)  != 0)
			company = companies[i];
	}
	
	date = substr($0, length($1) + 2);
}

$1 ~ /^[0-9]+$/ {
	printf("%s,%d,%d,%s,%s\n", $3, $1, $2, company, date);
}
'

logfile=$LOGDIR/latest-summary.txt
logfile2=$LOGDIR/latest-commits.txt
echo Will generate $logfile and $logfile2

# touch the logfiles w time
date > $logfile
echo "git, commits, files changed, insertions(+), deletions(-), total files, total lines" >> $logfile

date > $logfile2
echo "git, file changed, insertions(+), deletions(-), company, time" >> $logfile2

echoTotal () {
    sloc=0
    for i in $*; do
	let "sloc+=$i"
    done
    echo "$sloc" >> $logfile
}

parse2nd () {
    while read line; do
	echo $1,$line >> $logfile2
    done < "2nd.log"
}

while read line; do
    entry=$(echo $line | grep -c "project\ name")
    if [ $entry -ne 0 ]; then
 	name=$(echo $line | sed 's/.* name=\"//' | sed 's/\".*//')
	pentry=$(echo $line | grep -c "path=\"")
	if [ $pentry -eq 1 ]; then
 	    path=$(echo $line | sed 's/.* path=\"//' | sed 's/\".*//')
	else
	    path=$name
	fi  
	rev=$(echo $line | sed 's/.* revision=\"//' | sed 's/\".*//')
	if [ $PREV_MANIFEST ]; then
	    revbase=$(grep \"$name\" $PREV_MANIFEST | sed 's/.* revision=\"//' | sed 's/\".*//')
	else
	    revbase=
	fi
        echo -n "$name," >> $logfile
	cd $path
	if [ ! $revbase ]; then
	    git log --pretty=oneline --no-merges > one-line.log
	    revbase=$(tail -1 one-line.log | sed 's/ .*//')
	    rm -rf one-line.log
	fi
	if [ ! $rev = $revbase ]; then
	    echo -n $(git log --pretty=oneline --no-merges $revbase..$rev | wc -l), >> $logfile 
            echo -n $(git diff --shortstat $revbase $rev), | tr -d '[:alpha:] | [:space] | ( | ) | + | -' >> $logfile 
		# to create a second log
	    git log --numstat --no-merges --pretty='%ae %ci' $revbase..$rev |awk "$SCRIPT" > 2nd.log
	    parse2nd $name
	    rm -rf 2nd.log
	else
	    echo -n '0,0,0,0,' >> $logfile
	fi
        echo -n "$(find . -type f | xargs file --mime | grep "text\/" | sed 's/:.*//'| wc -l)," >> $logfile
	lines=$(find . -type f | xargs file --mime | grep "text\/" | sed 's/:.*//' | xargs wc -l | grep " total$" | sed 's/ total//')
	echoTotal $lines
	cd - >/dev/null
    fi
done < $CUR_MANIFEST

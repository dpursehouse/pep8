#!/bin/bash
#-x

# ----------------------------------------------------------------------------------------------------

treeName=[]
treeParent=[]
x=1

createTree () {

    for xmlfile in $xmlfiles ; do
	stopnode=`cat $xmlfile | grep MSM`
	
	aParent=0

	while read line; do
	    check=`echo $line | sed 's/ (.*)//m'`
	    if [ "a$check" == "a$line" ] ; then
		continue
	    fi
	    	
#	    xml=`echo $line | sed 's/ (.*)//m' | sed 's/[;|:]*//' | sed 's/\[.*]//'`
	    xml=`echo $line | sed 's/[;|:]*//' | sed 's/\[.*]//'`
	    xml=`echo $xml | sed 's/ /_____/m'`

	    treeName[$x]=$xml
	    treeParent[$x]="TOP"

	    if [ $aParent == 1 ] ; then
		treeParent[$[$x-1]]=${treeName[$x]}
	    fi

	    x=$[$x + 1]
	    
	    if [ "a$line" == "a$stopnode" ] ; then
		break
	    fi

	    aParent=1

	done < $xmlfile

    done

}

# ----------------------------------------------------------------------------------------------------

getChildren () {
    children=" "
    for (( i=1; i<$x; i++ )) ; do
	if [ "$1" == "${treeParent[$i]}" ] ; then
	    removeme=${treeName[$i]}
	    noalike=`echo $children | sed s/"$removeme"//m`
	    children="$noalike ${treeName[$i]}"
	fi
    done
}

makePretext () {
    if [ $1 == 0 ] ; then
	pretext=";"
    else
	pretext=`for i in $(seq $1); do echo -n ':'; done`
	pretext="$pretext[[File:1a.gif]]"
    fi
}

drawNode () {
    getChildren "$1"
    for child in $children ; do
	makePretext $2
	childtext=`echo $child | sed 's/_____/ /m'`
	echo "$pretext $childtext"
	drawNode "$child" $[$2+1]
    done
}

drawTree () {

    drawNode TOP 0

}

# ----------------------------------------------------------------------------------------------------

#/home/CORPUSERS/23052936/code2/script/blue_nv/cm_tools/parameter/wiki

here=`pwd`
path=$1

cd $path
xmlfiles=`ls *.layer.txt`
createTree
drawTree
cd $here
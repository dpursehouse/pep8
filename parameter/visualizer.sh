#!/bin/bash
#-x

# ----------------------------------------------------------------------------------------------------

getownerlist () {
    if [ -f $ownerfile ]; then
	rm $ownerfile
    fi
    ownerlist=https://wiki.sonyericsson.net/wiki_androiki/images/a/a5/$ownerfile
    wget -q $ownerlist
}

# ----------------------------------------------------------------------------------------------------
createwikitext () {
    owner=$here/$ownerfile
    products=`find $proddir -mindepth 1 -maxdepth 1 -type d`
    echo "== Product/band kombinations ==" > wiki/index.wiki.txt
	
    for d in $products ; do
	
	product=`basename "$d" | tr '[:upper:]' '[:lower:]' `;

        # The naming convention for band variants is:
        # <product>_[<bandnamealias>_][Cn][Ln][Wn][default_band]
	# More info:
	# https://wiki.sonyericsson.net/androiki/PLD_System_Core/Parameter_Handling/Blue#Naming_convention_for_band_variants
	bcfiles=`find $d/nv -regex ".*/${product}_\([a-z0-9]+_\)?\(C[0-9_]+\)?\(L[0-9_]+\)?\(W[0-9_]+\)?\(default_band\)?\.xml"`

	for bc in $bcfiles ; do
	    xmlfilename="${bc##*/}"
	    echo Working on $xmlfilename
	    newwikiname=`echo $xmlfilename | sed s/.xml//`
	    echo "([[$wikipage/$newwikiname/layer|View the layers]])" > wiki/$newwikiname.txt

	    ./visualizer.py $d/nv $xmlfilename $owner
	    cat wiki/$newwikiname.txt | ../semcwikitools/write_page.py "$wikipage/$newwikiname"
	    
	    newwikilayer=`./create_structure.py $d/nv $xmlfilename $owner`
	    cat wiki/$newwikilayer.layer.txt | ../semcwikitools/write_page.py "$wikipage/$newwikiname/layer"
	    
	    echo "[[$wikipage/$newwikiname|$newwikiname]]" >> wiki/index.wiki.txt
	    echo "''([[$wikipage/$newwikiname/layer|layers]])''<br>" >> wiki/index.wiki.txt
	
	done
    done

}

# ----------------------------------------------------------------------------------------------------

here=`pwd`
repopath=$1
wikipage=$2
ownerfile=$3
fsgenpath=$repopath/fsgen
datadir=$fsgenpath/data
proddir=$datadir/products

# Repo sync the modem source
cd $repopath
repo sync -q -j4
cd $here

# Create the wiki subfolder if it doesn't exist
if [ ! -d "wiki" ]; then
    mkdir wiki
fi

# Get the list of owners from the wiki
getownerlist

# Create the sub-wiki-pages
createwikitext

# Create the main-wiki-page
cat wiki/index.wiki.txt | ../semcwikitools/write_page.py $wikipage

echo All done!



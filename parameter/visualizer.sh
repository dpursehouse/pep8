#!/bin/bash
#-x

# -----------------------------------------------------------------------------
# visualizer.sh
#
# Usage: ./visualizer.sh <repopath> <wikipage> <ownerfile> <oldxml>
#         <repopath>  - Path to where the amss has been repo init'ed
#         <wikipage>  - What base page that should be used on the wiki
#         <ownerfile> - The name of the xml containing owners of NvItems
#         <oldxml>    - Where the xml files from the previous run are stored
#
# Parses through the fsgen git, searching for all product/band combination
# files, and creates two wiki pages for each. One by calling visualizer.py
# which has all the combined NvItem values from each included file. And another
# by calling create_structure.py that shows all xml files that are included by
# this combination (and the relation).
# This script also creates a wiki page that has a link to all subpages.
# -----------------------------------------------------------------------------

createwikitext () {
    owner=$here/$ownerfile
    find $proddir -mindepth 1 -maxdepth 1 -type d | sort > wiki/productdirs.txt
    echo "== Product/band combinations ==" > wiki/index.wiki.txt

    while read d ; do

        product=`basename "$d" | tr '[:upper:]' '[:lower:]' `;

        # The naming convention for band variants is:
        # <product>_[<bandnamealias>_][Cn][Ln][Wn][default_band]
        # More info:
        # https://wiki.sonyericsson.net/androiki/PLD_System_Core/...
        # Parameter_Handling/Blue#Naming_convention_for_band_variants
        re=".*/${product}_\([a-z0-9]+_\)?\(C[0-9_]+\)?\(L[0-9_]+\)?\(W[0-9_]+\)?\(default_band\)?\.xml"
        find $d/nv -regex $re | sort > wiki/bcfiles.txt

        partpath=`echo $d | sed 's/^.*data\/products/\/products/m'`
        echo ";$partpath" >> wiki/index.wiki.txt

        while read bc ; do
            xmlfilename="${bc##*/}"
            echo Working on $xmlfilename
            newwikiname=`echo $xmlfilename | sed s/.xml//`

            echo "__TOC__" > \
                wiki/$newwikiname.txt
            echo "== Parameter Snapshot ==" >> \
                wiki/$newwikiname.txt
            echo "* ([[$wikipage/$newwikiname/layer|View the layers]])" >> \
                wiki/$newwikiname.txt

            curl -f $oldxml/$newwikiname.xml -o wiki/$newwikiname.xml.old

            ./visualizer.py $d/nv/$xmlfilename $owner
            ./create_diff.py wiki/$newwikiname.xml.old wiki/$newwikiname.xml \
                $buildid >> wiki/$newwikiname.txt

            diffs=`tail -n 1 wiki/$newwikiname.txt`

            cat wiki/$newwikiname.txt | ../semcwikitools/write_page.py \
                "$wikipage/$newwikiname"

            newwikilayer=`./create_structure.py $d/nv/$xmlfilename`
            cat wiki/$newwikilayer.layer.txt | ../semcwikitools/write_page.py \
                "$wikipage/$newwikiname/layer"

            echo ":[[$wikipage/$newwikiname|$newwikiname]]" \
                "''([[$wikipage/$newwikiname/layer|layers]])''" \
                "''([[$wikipage/$newwikiname#Difference_between_" \
                "${oldbuildid}_and_${buildid}|$diffs]])''<br>" >> \
                wiki/index.wiki.txt

        done < wiki/bcfiles.txt

    done < wiki/productdirs.txt
}

# -----------------------------------------------------------------------------

here=`pwd`
repopath=$1
wikipage=$2
ownerfile=$3
oldxml=$4
fsgenpath=$repopath/fsgen
datadir=$fsgenpath/data
proddir=$datadir/products
buildid=`echo $wikipage | sed 's/^.*\///m'`

# Create the wiki subfolder if it doesn't exist
if [ ! -d "wiki" ]; then
    mkdir wiki
fi

# Get the previous build-id
curl -f $oldxml/buildid.txt -o wiki/buildid.txt.old

# If the previous build-id failed to get fetched or didn't exist, the previous
# build-id is unknown.
if [ ! -f "wiki/buildid.txt.old" ]; then
    echo "(unknown)" > wiki/buildid.txt.old
fi
oldbuildid=`cat wiki/buildid.txt.old`

# Create the sub-wiki-pages
createwikitext

# Add dependency-tree to the page
echo "{{XML_Dependency_Tree}}" >> wiki/index.wiki.txt
./make_tree.sh wiki >> wiki/index.wiki.txt

# Create the main-wiki-page
cat wiki/index.wiki.txt | ../semcwikitools/write_page.py $wikipage

echo All done!

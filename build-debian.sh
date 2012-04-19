#!/bin/sh -x
BRANCH=`git branch | sed -n "s/\* //p"`

dpkg-checkbuilddeps || exit 1

# git-dch requires an initial changelog
cp debian/changelog.orig debian/changelog
# Autogenerate version from git tags
DEBIAN_VERSION=`git describe --always --tags`
# Autogenerate changelog from git
START_OF_CHANGELOG=0ff2525daee943de85615737ad62738651ec24a7
EDITOR=/bin/true git-dch  --since $START_OF_CHANGELOG --debian-branch="$BRANCH" -N $DEBIAN_VERSION -R
# Build
dpkg-buildpackage
# Clean up
git checkout -- debian/changelog.orig
rm -f debian/changelog

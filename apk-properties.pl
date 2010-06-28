####################################################################
#
# Scan APK properties
#
# This script lists:
# LOCAL_PACKAGE_NAME (from Android.mk)
# project-name (from semcbuild.properties)
# LOCAL_CERTIFICATE (from Android.mk)
# certificate (from semcbuild.properties)
#
# help (switches):
#		"--all" for all apks even if no problems detected
#		"--no-tests" to skip /tests sub folders
#		"--check-semc" to only scan inside /semc subdirectories
#		"--ignore-testkey" to ignore cases where testkey would be used
#		if nothing is specified
#
# Starting point for scan is the current working directory.
# White space at front and end of strings are ignored.
#
####################################################################

use strict;
use File::Find;
use Cwd;

my @paths;
my @mkprops;
my @semcprops;
my $cwd = cwd;
my $cmdargs = "@ARGV";

find(sub { push @paths, $File::Find::dir if $_ eq 'AndroidManifest.xml' }, $cwd);

foreach my $aPath(@paths)
{
	my ($mkName, $mkCert) = ReadMkProperties($aPath);
	my ($semcName, $semcCert) = ReadSemcProperties($aPath);
	$aPath =~ s/\Q$cwd\E//g;

	# --no-tests specified as a command line argument will skip
	# output for all paths with "tests" in the path name
	if ($cmdargs =~ m/--no-tests/ and $aPath =~ m/tests/)
	{
		next;
	}
	# --check-semc specified as a command line argument will skip
	# output for all paths that do not contain "semc" in the path name
	if ($cmdargs =~ m/--check-semc/ and $aPath !~ m/semc/)
	{
		next;
	}
	# semcbuild.properties exists and does not contain
	# certificate testkey or name
	elsif ($semcName eq '' or ($semcCert eq '' and $cmdargs !~ m/--ignore-testkey/))
	{
		print "\nPath: $aPath\n";
		print "Error: Missing info in semcbuild.properties\n";
		print "LOCAL_PACKAGE_NAME: $mkName\n";
		print "project-name: $semcName\n";
		print "LOCAL_CERTIFICATE: $mkCert\n";
		print "certificate: $semcCert\n";
	}
	# Android.mk file exists and contains different values to
	# semcbuild.properties file
	elsif ($mkName ne 'Android.mk not found' and ($cmdargs !~ m/--ignore-testkey/ and $mkCert eq 'testkey' and $mkCert ne $semcCert or lc($mkName) ne lc($semcName)))
	{
		print "\nPath: $aPath\n";
		print "Error: Mismatch between Android.mk and semcbuild.properties\n";
		print "LOCAL_PACKAGE_NAME: $mkName\n";
		print "project-name: $semcName\n";
		print "LOCAL_CERTIFICATE: $mkCert\n";
		print "certificate: $semcCert\n";
	}
	# --all specified as a command line argument prints all info
	# where an AndroidManifest.xml file is found
	elsif ($cmdargs =~ m/--all/)
	{
		print "\nPath: $aPath\n";
		print "No problems detected\n";
		print "LOCAL_PACKAGE_NAME: $mkName\n";
		print "project-name: $semcName\n";
		print "LOCAL_CERTIFICATE: $mkCert\n";
		print "certificate: $semcCert\n";
	}
}

sub ReadMkProperties
{
	my ($iFile) = @_;
	open(SYSTEMFILE, "$iFile/Android.mk") or return 'Android.mk not found';
	my @content = <SYSTEMFILE>;
	close(SYSTEMFILE);
	my $mkName='';
	my $mkCert='';
	my @mkprops=();

	foreach my $LINE_VAR (@content)
	{
		if ($LINE_VAR =~ /LOCAL_PACKAGE_NAME := (.*$)/ )
		{
	    	$mkName = $1;
			unshift(@mkprops, trim($mkName));
		}
		elsif ($LINE_VAR =~ /LOCAL_CERTIFICATE := (.*$)/ )
		{
			$mkCert = $1;
			push(@mkprops, trim($mkCert));
		}
	}
	if ($mkName eq '')
	{
		unshift(@mkprops, '');
	}
	if ($mkCert eq '')
	{
		push(@mkprops, '');
	}
	return @mkprops;
}

sub ReadSemcProperties
{
	my ($iFile) = @_;
	open(SYSTEMFILE, "$iFile/semcbuild.properties") or return 'semcbuild.properties not found';
	my @content = <SYSTEMFILE>;
	close(SYSTEMFILE);
	my $semcName='';
	my $semcCert='';
    my @semcprops=();

	foreach my $LINE_VAR (@content)
	{
		if ($LINE_VAR =~ /project-name=(.*$)/ )
		{
	    	$semcName = $1;
			unshift(@semcprops, trim($semcName));
		}
		elsif ($LINE_VAR =~ /certificate=(.*$)/ )
		{
			$semcCert = $1;
			push(@semcprops, trim($semcCert));
		}
	}
	if ($semcName eq '')
	{
		unshift(@semcprops, '');
	}
	if ($semcCert eq '')
	{
		push(@semcprops, '');
	}
	return @semcprops;
}

# trim function to remove whitespace from the start and end of the string
sub trim($)
{
	my $string = shift;
	$string =~ s/^\s+//;
	$string =~ s/\s+$//;
	return $string;
}


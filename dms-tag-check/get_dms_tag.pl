use strict;
use warnings;
use Getopt::Long;
use CQPerlExt;

use constant MASTERSHIP_FIELD => "ratl_mastership";

my @CQ_Connection = ("CQMS.SE.SELD","CQMS.SE.JPTO","CQMS.SE.CNBJ");# ClearQuest Connection name
my $CQ_User_Db    = "DMS";      # Database (TSTX_ for Testing UTS_ for live)
my $CQ_user_name  = "xscm";     # ClearQUest user name
my $CQ_user_pw    = "3Yp(Wb%8"; # ClearQuest user password
my $CQ_Session;                 # ClearQuest Login Session
my $CQ_Login_Stat;              # ClearQuest Login Status
my $record;
my $fieldInfo;
my $temp;
my $status;
my $value;
my $server;
my $DMS_ID;
my $server_err = 0;
my $tag;
my $tags;
my @dms_tags;
my @dms_tags_found;
my $current_tag;
my @print_list;
my $print_str;
my $master_field;
my $server_name;
my @tmp_arr;

sub help {
    print "Usage: cqperl get_dms_tag.pl [--site SITE_LIST] [--help]\n";
    print "SITE_LIST: Site names should be comma separated\n";
    exit 0;
}
sub site_names{
    my $temp = $_[1];
    print $temp;
    $temp =~ s/([A-Z]*[A-Z])/CQMS.SE.$1/g;
    @CQ_Connection = split(/,/,$temp);
}

GetOptions ( 'site=s' => \&site_names,
             'help' => \&help);

open(MYINPUTFILE, "<DMS_tags.txt"); # open for input
my(@tags) = <MYINPUTFILE>; # read file into list
@tags = sort(@tags);

open(MYOUTFILE, ">dms_fix_for.txt");

$CQ_Session = CQPerlExt::CQSession_Build();
if (!$CQ_Session) {
    print "ClearQuest connect failed.\n";
}
else {
    print "Clearquest connected\n";
}
print @tags;
print "\n";
if (@tags) {
    foreach $server (@CQ_Connection) {
        print " Connecting to server " . $server ."\n";
        eval{
            $CQ_Session->UserLogon($CQ_user_name, $CQ_user_pw, $CQ_User_Db, $server);
            1;
        }or do {
            print "ClearQuest login failed.\n";
            $server_err = 1;
            next;
        };
        @tmp_arr = split(/\./,$server);
        $server_name = pop(@tmp_arr);
        print "Server mastership name: " . $server_name . "\n";
        foreach $tag (@tags) {
            chomp($tag);
            $DMS_ID = $tag;
            print "Searching DMS ID: " . $DMS_ID . "\n";
            print "Getting record reference \n";
            eval{
                $record = $CQ_Session->GetEntity("Issue", $DMS_ID);
                1;
            }or do {
                print "Record not available\n";
                unshift(@dms_tags, $DMS_ID);
                next;
            };
            print "Checking mastership \n";
            eval{
                $master_field = $record->GetFieldValue(MASTERSHIP_FIELD)->GetValue();
                print "Mastership site: " . $master_field . "\n";
                1;
            } or do {
                print "Error reading mastership field \n";
                unshift(@dms_tags, $DMS_ID);
                next;
            };
            if ( $master_field ne $server_name ) {
                print $server_name . " not having mastership \n";
                unshift(@dms_tags, $DMS_ID);
                next;
            }
            print "Getting fieldInfo reference \n";
            eval{
                $fieldInfo = $record->GetFieldValue("fix_for");
                1;
            }or do {
                print "Exception reading field value \n";
                unshift(@dms_tags, $DMS_ID);
                next;
            };
            $temp = $fieldInfo->GetValueStatus();
            if ($temp == $CQPerlExt::CQ_VALUE_NOT_AVAILABLE) {
                $status = "VALUE_NOT_AVAILABLE";
            } elsif ($temp == $CQPerlExt::CQ_HAS_VALUE) {
                $status = "HAS_VALUE";
                $value = $fieldInfo->GetValue();
                $print_str = $DMS_ID . ":" . $value;
                print $print_str . "\n";
                unshift(@print_list, $print_str);
                unshift(@dms_tags_found,$DMS_ID);
            } elsif ($temp == $CQPerlExt::CQ_HAS_NO_VALUE) {
                $status = "NO_VALUE";
                unshift(@dms_tags, $DMS_ID);
            } else {
                $status = "<invalid value status: " & $temp & ">";
                unshift(@dms_tags, $DMS_ID);
            }
            print "Status of query: " .$status . "\n";
        }
        #Updating tag list to search only for not found tags
        print "Updating the tag list\n";
        @tags = @dms_tags;
        @dms_tags = ();
        #Exit from outer loop if all tags are found
        if(!@tags) {
            last;
        }
    }
    print "DMS issues with tags: ";
    print @dms_tags_found;
    print "\n";
    print "DMS issues without tags: ";
    print @tags;
    print "\n";

    if ($server_err == 1){
        foreach $tag (@tags) {
            $print_str = $tag . ":Server_error";
            unshift(@print_list, $print_str);
        }
    }else {
        foreach $tag (@tags) {
            $print_str = $tag . ":Not found";
            unshift(@print_list, $print_str);
        }
    }

    foreach $tag (@print_list) {
        print MYOUTFILE $tag . "\n";
    }
}
close(MYOUTFILE);
close(MYINPUTFILE);


$CQ_Login_Stat = CQPerlExt::CQSession_Unbuild($CQ_Session);
print_file ("ClearQuest disconnect failed.") if ($CQ_Login_Stat);

__END__

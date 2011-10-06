use strict;
use warnings;
use Getopt::Long;
use CQPerlExt;

use constant CQ_EQ  => 1;
use constant CQ_OR  => 2;

use constant ISSUE_ENTITY => "Issue";
use constant ID_FIELD => "id";
use constant TITLE_FIELD => "title";
use constant MASTERSHIP_FIELD => "ratl_mastership";
use constant STATE_FIELD => "State";
use constant INTEGRATED_STATUS_FIELD => "integrated_status";
use constant VERIFIED_STATUS_FIELD => "verified_status";
use constant FIX_FOR_FIELD => "fix_for";


my @CQ_Connection = ("CQMS.SE.SELD","CQMS.SE.JPTO","CQMS.SE.CNBJ","CQMS.SE.USSV");# ClearQuest Connection name
my $CQ_User_Db    = "DMS";      # Database (TSTX_ for Testing UTS_ for live)
my $CQ_user_name  = "xscm";     # ClearQUest user name
my $CQ_user_pw    = "3Yp(Wb%8"; # ClearQuest user password
my $CQ_Session;                 # ClearQuest Login Session
my $CQ_Login_Stat;              # ClearQuest Login Status
my $query_def;
my $server_err=0;
my $result_set;
my $tag;
my @tmp_arr;
my $server_name;
my @dms_tags;
my $tmp;
my @print_list;
my @dms_tags_found;

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

open(MYOUTFILE, ">dms_fix_for.txt");

open(MYINPUTFILE, "<DMS_tags.txt") or  do {
    print "Error opening DMS_tags.txt \n";
    exit 0;
};# open for input
my(@tags) = <MYINPUTFILE>; # read file into list
@tags = sort(@tags);


$CQ_Session = CQPerlExt::CQSession_Build();
if (!$CQ_Session) {
    print "ClearQuest connect failed.\n";
}
else {
    print "Clearquest connected\n";
}
print @tags;
print "\n";
foreach $tag (@tags){
    chop($tag);
    unshift(@tmp_arr,$tag);
}
@tags = @tmp_arr;
if (@tags) {
    foreach my $server (@CQ_Connection) {
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

        $query_def = get_query_for_ids($CQ_Session, \@tags);
        if ($query_def == -1){
            next;
        }
        eval{
            $result_set = $CQ_Session->BuildResultSet($query_def);
            $result_set->EnableRecordCount();
            $result_set->Execute();
            1;
        }or do {
            print "Error running query\n";
            next;
        };
        #Parse the result set for the values needed for further processing and put them
        #in a hash in memory for fast queries
        my $issues_data = build_issue_hash($CQ_Session, $result_set, $query_def);

        foreach my $issue (keys(%{$issues_data})) {
            print "checking issue $issue\n";
            my %issue_h = %{$issues_data->{$issue}};
            print "Mastership:          " . $issue_h{MASTERSHIP_FIELD()} . "\n";
            print "State:               " . $issue_h{STATE_FIELD()} . "\n";
            print "Integrated Status:   " . $issue_h{INTEGRATED_STATUS_FIELD()} . "\n";
            print "Verified Status:     " . $issue_h{VERIFIED_STATUS_FIELD()} . "\n";
            print "Fix For:             " . $issue_h{FIX_FOR_FIELD()} . "\n";

            #TODO: check mastership changed during checking
            if($issue_h{MASTERSHIP_FIELD()} ne $server_name){
                print $server_name . " not having mastership \n";
                unshift(@dms_tags, $issue);
                next;
            }
            $tmp = $issue . ",";
            $tmp = $tmp . "Mastership:" . $issue_h{MASTERSHIP_FIELD()} . ",";
            $tmp = $tmp . "State:" . $issue_h{STATE_FIELD()} . ",";
            $tmp = $tmp . "Integrated Status:" . $issue_h{INTEGRATED_STATUS_FIELD()} . ",";
            $tmp = $tmp . "Verified Status:" . $issue_h{VERIFIED_STATUS_FIELD()} . ",";
            if($issue_h{FIX_FOR_FIELD()} ne ""){
                $tmp = $tmp . "Fix For:" . $issue_h{FIX_FOR_FIELD()};
            }else {
                $tmp = $tmp . "Fix For:Not Found";
            }
            unshift(@print_list, $tmp);
            unshift(@dms_tags_found,$issue);
        }
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
            $tmp = $tag . ",Server_error";
            unshift(@print_list, $tmp);
        }
    }else {
        foreach $tag (@tags) {
            $tmp = $tag . ",";
            $tmp = $tmp . "Mastership:None,";
            $tmp = $tmp . "State:None,";
            $tmp = $tmp . "Integrated Status:None,";
            $tmp = $tmp . "Verified Status:None,";
            $tmp = $tmp . "Fix For:Not Found";
            unshift(@print_list, $tmp);
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



#######################################
#  get_query_for_ids                  #
#  Generates a cq query object for a  #
#  list of issue ids.                 #
#  Takes a cq session object and a    #
#  ref to an issue array as input.    #
#  Returns a cq query object.         #
#######################################

sub get_query_for_ids {
    my $session = shift @_;
    my $issues_ref = shift @_;
    my $query;
    eval{
        # Build Query
        $query = $session->BuildQuery(ISSUE_ENTITY);
        $query->BuildField(ID_FIELD);
        $query->BuildField(TITLE_FIELD);
        $query->BuildField(MASTERSHIP_FIELD);
        $query->BuildField(STATE_FIELD);
        $query->BuildField(INTEGRATED_STATUS_FIELD);
        $query->BuildField(VERIFIED_STATUS_FIELD);
        $query->BuildField(FIX_FOR_FIELD);

        my $filter_node = $query->BuildFilterOperator(CQ_OR);

        $filter_node->BuildFilter(ID_FIELD, CQ_EQ, \@{$issues_ref});
        1;
    } or do {
        print "Error in defining query \n";
        $query=-1;
    };
    return $query;
}

#######################################
# build_issue_hash                    #
# Returns a hash ref containing issue #
# paired with hash ref containining   #
# issue fields and values.            #
#######################################

sub build_issue_hash {
  my $session = shift @_;
  my $result_set = shift @_;
  my $query_def = shift @_;

  my %hash;

  my @fields = (MASTERSHIP_FIELD,STATE_FIELD,INTEGRATED_STATUS_FIELD,
                VERIFIED_STATUS_FIELD,FIX_FOR_FIELD);

  my $id_column = is_field_in_query($query_def, ID_FIELD);
  if($id_column == 0) {
    print "Could not get column for DMS ID\n";
  }

  my %columns;
  my $field;
  foreach $field (@fields) {
    my $column = is_field_in_query($query_def, $field);
    if($column == 0) {
      print "Could not get column for " . $field . "\n";
    }
      $columns{$field} = $column;
  }

  while ($result_set->MoveNext() == $CQPerlExt::CQ_SUCCESS){
    eval {
      my $issue_id = $result_set->GetColumnValue($id_column);
      $hash{$issue_id} = ();
      foreach $field (@fields) {
        my $field_value = $result_set->GetColumnValue($columns{$field});
        if(!defined($field_value)) {
          $field_value = "";
          print "Could not get value in field" . $field . "for issue" .  $issue_id . "\n";
        }
        $hash{$issue_id}->{$field} = $field_value;
      }
    };
     if($@ ne "") {
       print "Could not get data from result set.";
       print "$@\n";
     }
  }
  return \%hash;
}
#######################################
#  is_field_in_query                  #
#  Checks if a certain field is part  #
#  of a query. Takes a query object   #
#  and a field name as input.         #
#  Returns true if the field is in,   #
#  false if not.                      #
#######################################

sub is_field_in_query {
  my $query = shift @_;
  my $field_name = shift @_;

  #Iterate over the field defs in the query and
  #check if the searched field is defined in the
  #query.
  my $query_field_defs = $query->GetQueryFieldDefs();
  for(my $i = 0; $i < $query_field_defs->Count(); $i++) {
    my $query_field_def = $query_field_defs->Item($i);
    my $current_field = $query_field_def->GetFieldPathName();
    if($current_field eq $field_name) {
      return $i+1;
    }
  }

  #For now, assume that the field is not in the query.
  #Todo: logic for figuring out when a certain field is actually
  #in the query.
  return 0;
}

__END__

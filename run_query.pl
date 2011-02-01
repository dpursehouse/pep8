#!/usr/bin/perl

use strict;
use warnings;

use CQPerlExt;

use Win32::OLE;

use Getopt::Long;

use constant CQ_AND => 1;
use constant CQ_EQ  => 1;
use constant CQ_OR  => 2;
use constant CQ_NO_DATA => 2;

use constant DB => "DMS";
use constant GENERAL_SCHEMA => "CQMS.SE.";
use constant USRT => "USRT"; #RTP
use constant JPTO => "JPTO"; #Tokyo
use constant CNBJ => "CNBJ"; #Beijing
use constant SELD => "SELD"; #Lund
use constant USSV => "USSV"; #Redwood
use constant MASTERSHIP_FIELD => "ratl_mastership";
use constant ID_FIELD => "id";
use constant TITLE_FIELD => "title";
use constant ISSUE_ENTITY => "Issue";
use constant SW_LABEL_ENTITY => "SW_label";
use constant DMS_ID_LABEL => "DMS ID";
use constant MASTER_LABEL => "ratl_mastership";
use constant RELEASE_LABEL_FIELD => "sw_official_release";
use constant STATE_FIELD => "State";
use constant INTEGRATED_STATUS_FIELD => "integrated_status";
use constant VERIFIED_STATUS_FIELD => "verified_status";
use constant FIX_FOR_FIELD => "fix_for";
use constant PROJ_ID => "proj_id";
use constant RESTRICTED_STATE => "Integrated";
use constant FINAL_STATE => "Verified";
use constant PREFERRED_STATUS => "Test OK";
use constant DEFAULT_SITE => SELD;
use constant STATE_ACTION => "Pass";

use constant ERROR => "[ERROR]";
use constant WARN => "[WARNING]";
use constant CQERROR => "[CQERROR]";
use constant OK => "[OK]";
 
my $query;
my $log_file;
my $label;
my $user;
my $pwd;
my @issues;
my $list;
my $update;
my @sites;
my $unverified_query;
my $unlabeled_query;
my $project;

my $options_ok;
my $log_handle;

my $do_log = 1;

################################################################################
#              ARGUMENT PARSING STARTS HERE!!!                                 #
################################################################################

#If no arguments are supplied, prompt for values.
if(scalar(@ARGV) == 0) {
  my $rerun = 1;
  while($rerun) {
    print "Enter user: ";
    $user = <STDIN>;
    chomp $user;
  
    print "Please enter your password: ";
    $pwd = <STDIN>;
    chomp $pwd;
  
    print "Enter log file: ";
    $log_file = <STDIN>;
    chomp $log_file;
  
    # Choose if an exported query or a list of issues should be used for querying CQ.
    # 1 for query, 2 for issue list (comma separated).
    print "Do you want to use a saved query or an issue list (issue1, issue2...)?\n";
    print "1) for query\n";
    print "2) for issues\n";
    my $choice = 0;
    while(!($choice == 1 || $choice == 2)){
      print "Enter 1/2): ";
      $choice = <STDIN>;
      chomp $choice;
      if($choice == 1) {
        print "Enter query path: ";
        $query = <STDIN>;
        chomp $query;
      } elsif ($choice == 2) {
        print "Enter issue list (comma separated): ";
        my $issue_list = <STDIN>;
        chomp $issue_list;
        @issues = split(/,/, $issue_list);
      }
    }

    # Choose if records should be updated or label value listed.
    # 1 for list, 2 for update.
    $choice = 0;
    while(!($choice == 1 || $choice == 2)){
      print "List or Update?\n";
      print "1) For list\n";
      print "2) for update\n";
      $choice = <STDIN>;
      if($choice == 1) {
        $list = 1;
        print "Enter path to unverified query (generated). Empty for no query.\n";
        my $path = <STDIN>;
        if($path ne "") {
          $unverified_query = $path;
        }
      } elsif ($choice == 2) {
        $update = 1;
        # If update, a label to update each record with is needed.
        print "Enter label: ";
        $label = <STDIN>;
        chomp $label;
      } else {
        print "Enter 1 for list or 2 for update:\n";
      }
    }
    
    # A list of sites to run on. Necessary if update is selected and there are
    # issues mastered on other sited.
    print "Enter site(s) (comma speparated list):\n";
    my $sites_list = <STDIN>;
    chomp $sites_list;
    @sites = split(/,/, $sites_list);

    # Project (Technical name) refers to the name of project that the label should exist in.
    # Necessary if a label should be created.
    $choice = 0;
    while(!($choice == 1 || $choice == 2)){
      print "Create SW label?\n";
      print "1) Create SW label\n";
      print "2) Skip creation of SW label\n";
      $choice = <STDIN>;
      if($choice == 1) {
        print "Enter project (Technical name):\n";
        my $project = <STDIN>;
        chomp $project;
        if($project eq "") {
          print "Please enter a non-empty string";
          undef $project;
          $choice = 0;
        }
      } elsif ($choice == 2) {
        ;
      } else {
        print "Enter 1 Create SW label or 2 to skip creation of SW label:\n";
      }
    }

    # Print all inputed parameters.
    print "Chosen parameters:";
    print "User = ", $user, "\n";
    print "Pwd = ", $pwd, "\n";
    if(defined($label)) {
      print "Label = ", $label, "\n";
    }
    print "Log file = ", $log_file, "\n";
    if(defined($query)) {
      print "Query = ", $query, "\n";
    } elsif (@issues) {
      print "Issues = ", join(',', @issues), "\n";
    }
    if(defined($update)) {
      print "Update = On\n";
    } elsif (defined($list)) {
      print "List = On\n";
    }
    if(defined($unverified_query)) {
      print "Unverified query: $unverified_query\n";
    } else {
      print "No unverified query generated!\n";
    }
    print "Sites: ", join(', ', @sites), "\n";
    
    # Query user if input is ok. Offer to rerun if not.
    my $done = "";
    while(!($done =~ /^y(es)?/ || $done =~ /^no?/)) {
      print "Options Ok? (y[es]/n[o]): ";
      $done = <STDIN>;
      chomp $done;
      if($done =~ /^y(es)?/) {$rerun = 0;}
      if($done =~ /^no?/) {$rerun = 1;}
    }
  }
# Parse command line arguments if such were provided.
} else {
  $options_ok = GetOptions("query=s"        => \$query,
                            "log=s"         => \$log_file,
                            "label=s"       => \$label,
                            "pwd=s"         => \$pwd,
                            "user=s"        => \$user,
                            "list"          => \$list,
                            "update"        => \$update,
                            "sites=s"       => \@sites,
                            "unv=s"         => \$unverified_query,
                            "unl=s"         => \$unlabeled_query,
                            "issues=s"      => \@issues,
                            "createlabel=s" => \$project);

  die usage() unless ($options_ok && $log_file && $pwd && $user && ($query || @issues));
  if(@issues) {
    @issues = split(/,/, join(',', @issues));
  }
  if(@sites) {
    @sites = split(/,/, join(',', @sites));
  } else {
    push(@sites, DEFAULT_SITE);
  }
  if(defined($update)&& !defined($label)) {
    die usage();
  }
  if(defined($update) && defined($list)) {
    die usage();
  }
  if(defined($project) && !defined($label)) {
    die usage();
  }
}


################################################################################
#              ARGUMENT PARSING ENDS HERE!!!                                   #
################################################################################

$| = 1;

logg(OK, "Starting run!");

my $site = $sites[0];
my $current_site;

# If $site is a site that can not be handled by this script, site_exists
# will logg a warning about this.
site_exists($site);

my $session = get_session($site);
if($session == -1) {
  print "Error with site $site";
  logg(ERROR, "Could not get a session for site $site");
}

#Create SW label only on site $sites[0], label should be synchronised to other
#sites within 30 minutes
if(defined($project) && defined($label)) {
  create_sw_label($session,$project,$label);
}

#If a query is provided, make sure it has all the necessary fields
#defined. If not, add the fields.
#If no query is provided, generate on with the necessary fields.
my $query_def;
if(defined($query)) {
  #Get the query from file
  $query_def = $session->OpenQueryDef($query);
  #If mastership is not in the query, add that.
  foreach my $field (MASTERSHIP_FIELD,
                     STATE_FIELD,
                     INTEGRATED_STATUS_FIELD,
                     VERIFIED_STATUS_FIELD,
                     RELEASE_LABEL_FIELD,
                     PROJ_ID,
                     FIX_FOR_FIELD) {
    if(!is_field_in_query($query_def, $field)) {
      $query_def->BuildField($field);
    }
  }
} elsif (scalar(@issues) > 0) {
  $query_def = get_query_for_ids($session, \@issues);
} else {
  usage();
}

#CQPerlExt seemed to be confused unless the generated/modified query was not
#first saved too disk and then re-read.
my $query_path = "$site" . "_generated_" . create_time_stamp() . ".qry";
$query_def->Save($query_path);
$query_def = undef;
$query_def = $session->OpenQueryDef($query_path);

my $result_set = $session->BuildResultSet($query_def);
$result_set->EnableRecordCount();
$result_set->Execute();
	
if (Win32::OLE->LastError != 0) {
  print "Problem with DMS Query\n";
  $session->SignOff();
}

if(!defined($result_set)) {
  logg(ERROR, "Could not get query result for site $site");
  $session->SignOff();
}

#Parse the result set for the values needed for further processing and put them
#in a hash in memory for fast queries
my $issues_data = build_issue_hash($session, $result_set, $query_def, MASTERSHIP_FIELD,
                                                                      RELEASE_LABEL_FIELD,
                                                                      STATE_FIELD,
                                                                      INTEGRATED_STATUS_FIELD,
                                                                      VERIFIED_STATUS_FIELD,
                                                                      PROJ_ID,
                                                                      FIX_FOR_FIELD);

if(defined($list)) {
  list($issues_data);
  if(defined($unverified_query)) {
    my $unverified = get_unverified($issues_data);
    my $unver_number = scalar(@{$unverified});
    print "Found $unver_number unverified issues.\n";
    if($unver_number > 0) {
      generate_partial_query($unverified, $unverified_query, $session);
    }
  } elsif(defined($unlabeled_query)) {
    my $unlabeled = get_unlabeled($issues_data);
    my $unl_number = scalar(@{$unlabeled});
    print "Found $unl_number unlabeled issues.\n";
    if($unl_number > 0) {
      generate_partial_query($unlabeled, $unlabeled_query, $session);
    }
  
  }
  $session->SignOff();
}

if(defined($update) && defined($label)){
  update($session, $issues_data);
}

logg(OK, "Done for this time. Good bye!");

exit(0);

################################################################################
#                SUBS AFTER THIS SECTION!!!                                    #
################################################################################

#######################################
#  get_session                        #
#  Returns a CQ session object with   #
#  a site and schema as input.        #
#  Returns -1 if an error occurs.     #
#######################################

sub get_session {
  my $site = shift @_;
  my $schema = GENERAL_SCHEMA . $site;
  logg(OK, "Starting log on to site $site");
  print create_time_stamp(), " Logging on site $site. Please wait!\n";
  my $CQSession = Win32::OLE->new("ClearQuest.Session");
  
  if (Win32::OLE->LastError != 0) {
    logg(ERROR, "Problem with access to ClearQuest API (OLE Object)");
    return -1;
  }
  $CQSession->UserLogon($user, $pwd, DB, 2, $schema);
  
  if (Win32::OLE->LastError != 0) {
    $CQSession->SignOff();
    logg(ERROR, "Could not start session with schema $schema and site $site");
    return -1;
  }
  logg(OK, "New session for site $site started");
  print create_time_stamp(), " Logged on site $site!\n";
  $current_site = $site;
  return $CQSession;
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
  
  my @fields;
  if(scalar(@_) >= 1) {
    @fields = @_;
  }
  
  my $id_column = is_field_in_query($query_def, ID_FIELD);
  if($id_column == 0) {
    logg(ERROR, "Could not get column for " . DMS_ID_LABEL);
  }
  
  my %columns;
  my $field;
  foreach $field (@fields) {
    my $column = is_field_in_query($query_def, $field);
    if($column == 0) {
      logg(ERROR, "Could not get column for " . $field);
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
          logg(WARN, "Could not get value in field $field for issue $issue_id");
        }
        $hash{$issue_id}->{$field} = $field_value;
      }
    };
     if($@ ne "") {
       logg(WARN, "Could not get data from result set.");
       logg(CQERROR, "$@\n");
     }
  }
  return \%hash;
}

#######################################
# list                                #
# Prints a list of issues with the    #
# fields and values defined in the    #
# issue hash                          #
#######################################

sub list {
  my $issues_data = shift @_;
  my $first_line = 1;
  print "Issue : ";
  foreach my $issue (keys(%{$issues_data})) {
      if($first_line) {
        foreach my $field (keys(%{$issues_data->{$issue}})) {
          print "$field : ";
        }
        print "\n";
      }
      print "$issue : ";
      foreach my $field (keys(%{$issues_data->{$issue}})) {
        print $issues_data->{$issue}->{$field}, " : ";
    }
    $first_line = 0;
    print "\n";
  }
}


#######################################
# update                              #
# Updates the verified issues with    #
# Official SW release according to    #
# the label entered as option         #
#######################################

sub update {
  my $session     = shift @_;
  my $issues_data = shift @_;

  my @unverified;
  my %site_issues = (
                      SELD => [],
                      JPTO => [],
                      CNBJ => [],
                      USSV => []
                    );

  my %site_issues_update_state = (
                                   SELD => [],
                                   JPTO => [],
                                   CNBJ => [],
                                   USSV => []
                                 );

  my $technical_name = label_is_valid($session,$label);
  if ((!$technical_name) || ($technical_name eq "-1")) {
    return -1;
  }

  foreach my $issue (keys(%{$issues_data})) {
    print "checking issue $issue\n";
    my %issue_h = %{$issues_data->{$issue}};
    if ($issue_h{PROJ_ID()} eq $technical_name) {
      if(($issue_h{STATE_FIELD()} eq RESTRICTED_STATE) && ($issue_h{INTEGRATED_STATUS_FIELD()} eq PREFERRED_STATUS)){
        push(@{$site_issues{$issue_h{MASTER_LABEL()}}}, $issue);
        push(@{$site_issues_update_state{$issue_h{MASTER_LABEL()}}}, $issue);
      } elsif($issue_h{STATE_FIELD()} eq FINAL_STATE) {
        if ($issue_h{VERIFIED_STATUS_FIELD()} eq PREFERRED_STATUS) {
          if ($issue_h{RELEASE_LABEL_FIELD()} eq "") {
            push(@{$site_issues{$issue_h{MASTER_LABEL()}}}, $issue);
          } else {
            push(@unverified, $issue);
            logg(WARN, "Skipping issue $issue with state \"" . FINAL_STATE . " " . PREFERRED_STATUS . "\" due to SW Official Release field already filled in");
          }
        } else {
          push(@unverified, $issue);
          logg(WARN, "Skipping issue $issue with state \"$issue_h{STATE_FIELD()}\" because \"" . VERIFIED_STATUS_FIELD ."\" not equal to \"" . PREFERRED_STATUS . "\"");
        }
      } else {
        push(@unverified, $issue);
        logg(WARN, "Skipping issue $issue with state \"$issue_h{STATE_FIELD()}, $issue_h{INTEGRATED_STATUS_FIELD()}\" != \"" . RESTRICTED_STATE . " " . PREFERRED_STATUS . "\"");
      }
    }else {
      push(@unverified, $issue);
      logg(WARN, "Skipping issue $issue, DMS issue proj_id: $issue_h{PROJ_ID()} is not equal to label technical_name:$technical_name");
    }
  }
  DO_SITES:
  foreach $site (@sites) {
    if(!site_exists($site)) {
      next DO_SITES;
    }
    if(scalar(@{$site_issues{$site}}) == 0) {
      print "No issues for site $site\n";
      logg(OK, "No issues for site $site");
      next DO_SITES;
    }
    if($site ne $current_site) {
      $session->SignOff();
      $session = -1;
      print "Done with site $current_site\n";
      logg(OK, "Done with site $current_site");
      $session = get_session($site);
        if($session == -1) {
          print "Error with site $site";
          logg(ERROR, "Could not get a session for site $site");
          next DO_SITES;
        }
    }
    if(scalar(@{$site_issues_update_state{$site}}) > 0) {
      change_state_issues($session, $site_issues_update_state{$site}, STATE_ACTION, PREFERRED_STATUS);
    }
    modify_issues($session, $site_issues{$site}, $label);
  }
  $session->SignOff();
  logg(OK, "Logged off site $current_site");
  my $unverified_number = scalar(@unverified);
  logg(OK, "Found $unverified_number unverified issues");
  if($unverified_number > 0) {
    generate_partial_query(\@unverified, "");
  }
}

#######################################
# get_unverified                      #
# Finds all unverified issues and     #
# returns an array ref to a list of   #
# the same.                           #
#######################################

sub get_unverified {
  my $issues_data = shift @_;
  
  my @unverified;
  
  foreach my $issue (keys(%{$issues_data})) {
    my $state = $issues_data->{$issue}->{'State'};
    if( $state ne "Verified") {
      #print "Unverified issue $issue with state $state found.\n";
      push(@unverified, $issue);
    }
  }
  return \@unverified;
}


#######################################
# get_unlabeled                       #
# Filters out all issues with empty   #
# sw_official_release field.          #
#######################################

sub get_unlabeled {
  my $issues_data = shift @_;
  
  my @unlabeled;
  
  foreach my $issue (keys(%{$issues_data})) {
    my $label = $issues_data->{$issue}->{'sw_official_release'};
    if( $label eq "") {
      #print "Unlabeled issue $issue found.\n";
      push(@unlabeled, $issue);
    }
  }
  return \@unlabeled;
}

#######################################
# generate_unverified_query           #
# generates a query file for the un-  #
# verified issues provided in an      #
# array ref.                          #
#######################################

sub generate_partial_query {
  my $partial_ref = shift @_;
  my $query_file = shift @_;
  if($query_file eq "") {
    if(defined($label)) {
      $query_file = "generated_" . $label ."_" . create_time_stamp() . ".qry";
    } else {
      $query_file = "generated_" . create_time_stamp() . ".qry";
    }
  }
  my $session;
  my $do_logoff = 0;
  if(scalar(@_) > 0) {
    $session = shift @_;
  } else {
    $session = get_session($sites[0]);
    if($session == -1) {
      print "Error with site $site";
      logg(ERROR, "Could not get a session for site $site");
    }
    $do_logoff = 1;
  }
    my $partial_issues_query = get_query_for_ids($session, $partial_ref);
    $partial_issues_query->Save($query_file);
    logg(OK, "Generated query saved as $query_file");
    print "Saved generated query $query_file!\n";
    if($do_logoff) {
      logg(OK, "Logging off site $sites[0]");
      print create_time_stamp(), "Logging off site $sites[0]\n";
      $session->SignOff();
    }
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
  my $query_field_defs = $query->QueryFieldDefs();
  for(my $i = 0; $i < $query_field_defs->Count(); $i++) {
    my $query_field_def = $query_field_defs->Item($i);
    my $current_field = $query_field_def->FieldPathName();
    if($current_field eq $field_name) {
      return $i+1;
    }
  }
  
  #For now, assume that the field is not in the query.
  #Todo: logic for figuring out when a certain field is actually
  #in the query.
  return 0;
}

#######################################
#  list_label_for_ids                 #
#  Lists the "Official SW Release"    #
#  field for all issues provided.     #
#  Takes a session object and a ref   #
#  to an array of issue ids as input. #
#  No return value, loggs errors.     #
#######################################

sub list_label_for_ids {
  my $session = shift @_;
  my $issues_ref = shift @_;
  
  my @issues = @{$issues_ref};
  
  foreach my $issue (@issues) {
    my $record;
    eval {
      $record = $session->GetEntity(ISSUE_ENTITY, $issue);
    };
    if($@ eq "") {
      print $issue, " = ";
      eval {
        print $record->GetFieldValue(RELEASE_LABEL_FIELD)->GetValue(), "\n";
      };
      if($@ ne "") {
        logg(WARN, "Could not get label for $issue");
        logg(CQERROR, "$@\n");
      }
    } else {
      logg(WARN, "Could not find issue $issue");
      logg(CQERROR, "$@\n");
    }
  }
}

#######################################
#  get_column                         #
#  Finds the column number in a       #
#  result set for a certan field.     #
#  Returns the column number.         #
#  Returns 0 if not found or -1 if an #
#  error ocurred.                     #
#######################################

sub get_column {
  my $session = shift @_;
  my $result_set = shift @_;
  my $column_label = shift @_;
  my $found_column;
	
	my $column = 1;
	eval {
    my $no_of_columns = $result_set->GetNumberOfColumns();
    while($column <= $no_of_columns) {
      my $column_name = $result_set->GetColumnLabel($column);
      if ($column_name =~ /$column_label/) {
        $found_column = $column;
      }
      $column++;
    }
  };
  if($@ eq "") {
    if(defined($found_column)) {
      return $found_column;
    } else {
      logg(ERROR, "Could not find column for column label $column_label");
      return 0;
    }
  } else {
    logg(ERROR, "Error while looking for $column_label");
    logg(CQERROR, "$@\n");
    return -1;
  }
}

#######################################
#  label_is_valid                     #
#  Checks if a certain release label  #
#  is available in DMS so that it can #
#  be used to put on an issue.        #
#  takes a cq session object and a    #
#  label as input.                    #
#  Returns technichal_name of label   #
#  object if label exist, -1 if label #
#  doesn't exist and 0 for error      #
#######################################

sub label_is_valid {
  my $session = shift @_;
  my $label   = shift @_;
  my $label_from_record;
  my $technical_name;

  eval {
    $label_from_record = $session->GetEntity(SW_LABEL_ENTITY, $label);
  };
  if($@ eq "") {
    if ($label_from_record) {
      eval {
        $technical_name = $label_from_record->GetFieldValue('technical_name')->GetValue();
      };
      if($@ ne "") {
        logg(ERROR, "Failed to get technical name of label $label");
        logg(CQERROR, "$@\n");
        return 0;
      } else {
        return $technical_name;
        logg(OK, "Retrieved technical_name $technical_name from label $label");
      }
    } else {
      logg(WARN, "Label $label doesn't exist");
      return -1;
    }
  } else {
    logg(ERROR, "Failed to validate label $label");
    logg(CQERROR, "$@\n");
	return 0;
  }
}

#######################################
#  is_master                          #
#  Checks if a site has mastership of #
#  a certain record.                  #
#  Takes a record object and a site   #
#  as input. Returns 1 if site is     #
#  master, 0 if not and -1 if error   #
#  ocurrs.                            #
#######################################  

sub is_master {
  my $record = shift @_;
  my $this_site = shift @_;
  
  my  $master_status;
  
  eval {
    $master_status = ($record->GetFieldValue(MASTERSHIP_FIELD)->GetValue() eq $this_site);
  };
  
  if($@ eq "") {
    return $master_status;
  } else {
    logg(ERROR, "Failed to get mastership for site $this_site");
    logg(CQERROR, "$@");
    return -1;  
  }
}

#######################################
# create_sw_label                     #
# Creates a new SW_label entity       #
# Takes cq session, project and label #
# name as input.                      #
# Returns 1 if created, 0 on error    #
# and -1 not created (already exist)  #
#######################################

sub create_sw_label {
  my $session = shift @_;
  my $project = shift @_;
  my $label   = shift @_;

  #Stop if label already exist.
  #Continue to create label otherwise.
  my $createlabel = label_is_valid($session,$label);
  if(!$createlabel) {
    return 0;
  } elsif ($createlabel ne "-1") {
    return -1;
  }

  my $entityObj;
  eval {
    $entityObj = $session->BuildEntity(SW_LABEL_ENTITY);
  };
  if($@ ne "") {
    logg(ERROR, "Can not Build entity SW_LABEL_ENTITY");
    logg(CQERROR, "$@\n");
    return 0;
  }
  eval {
    $entityObj->SetFieldValue("name", $label);
  };
  if($@ ne "") {
    logg(ERROR, "Can not set $label in name field ");
    logg(CQERROR, "$@\n");
    return 0;
  }

  eval {
    $entityObj->SetFieldValue("technical_name", $project);
  };
  if($@ ne "") {
    logg(ERROR, "Can not set $project in technical_name field ");
    logg(CQERROR, "$@\n");
    return 0;
  }
  eval {
    $entityObj->SetFieldValue("hw", "0");
  };
  if($@ ne "") {
    logg(ERROR, "Can not set 0 in hw field ");
    logg(CQERROR, "$@\n");
    return 0;
  }

  my $status;
  eval {
    $status = $entityObj->Validate();
  };
  if(($@ ne "") && ($status ne "")) {
    logg(ERROR, "Can not validate adding new label $label!");
    logg(CQERROR, "$@\n");
    return 0;
  }

  eval {
    $status = $entityObj->Commit();
  };
  if(($@ ne "") && ($status ne "")) {
    $entityObj->Revert();
    logg(ERROR, "Failed to create $label!");
    logg(CQERROR, "$@\n");
    return 0;
  } else {
    my $msg = "Created label $label";
    logg(OK, $msg);
    print "$msg\n";
    return 1;
  }
}

#######################################
#  modify_label                       #
#  Modifies the "Official SW Release" #
#  field of an issue record.          #
#  Takes as input a cq session object #
#  an issue and a label.              #
#  Returns 1 if ok,0 if not exist,    #
#  -1 on error.                       #
#######################################

sub modify_label {
  my $session = shift @_;
  my $issue = shift @_;
  my $label = shift @_;
  
  my $record;
  eval {
    $record = $session->GetEntity(ISSUE_ENTITY, $issue);
  };
  if($@ ne "") {
    logg(ERROR, "Can not get record for issue $issue");
    logg(CQERROR, "$@\n");
    return -1;
  } elsif($record eq ""){
    logg(WARN, "Issue $issue doesn't exist");
    return 0;
  }
  
  my $ret = modify($session, $record, RELEASE_LABEL_FIELD, $label);
  if($ret == 0 || $ret == -1) {
    logg(ERROR, "Can not modify record for issue $issue");
    return -1;
  } else {
    logg(OK, "Modified record for issue $issue");
    return 1;
  }
}
#######################################
#  change_state                       #
#  Changes the state of an issue      #
#  record.                            #
#  Takes a cq session object, a ref   #
#  to an issues array and a           #
#  state_action and status as input.  #
#  Returns 1 if ok,0 if issue doesn't #
# exist, -1 on error.                 #
#######################################

sub change_state {
  my $session      = shift @_;
  my $issue        = shift @_;
  my $state_action = shift @_;
  my $status       = shift @_;

  my $record;
  eval {
    $record = $session->GetEntity(ISSUE_ENTITY, $issue);
  };
  if($@ ne "") {
    logg(ERROR, "Can not get record for issue $issue");
    logg(CQERROR, "$@\n");
    return -1;
  } elsif($record eq "") {
    logg(WARN, "Issue $issue doesn't exist");
    return 0;
  }

  my $ret = change($session, $record, $state_action, VERIFIED_STATUS_FIELD, $status );
  if($ret == 0 || $ret == -1) {
    logg(ERROR, "Can not update state for issue $issue");
    return -1;
  } else {
    logg(OK, "Changed state for issue $issue");
    return 1;
  }

}

#######################################
#  modify                             #
#  Sets a field to a value in a       #
#  record.                            #
#  Inputs: a CQ session, a record,    #
#  a field and a value.               #
#  Returns 1 if change can be         #
#  commited, -1 on error.             #
#######################################

sub modify {
  my $session = shift @_;
  my $record  = shift @_;
  my $field   = shift @_;
  my $value   = shift @_;
  
  my $mastership = is_master($record, $current_site);
  
  if($mastership == -1) {
    logg(ERROR, "Error while retreiving mastership status for site $current_site");
    return -1;
  }
  if(!$mastership) {
    logg(ERROR, "Does not have mastership for change of field $field to value $value");
    return 0;
  }
  
  eval {
    $session->EditEntity($record, "modify");
  };
  if($@ ne "") {
    logg(ERROR, "Can not make record editable to set $field = $value");
    logg(CQERROR, "$@\n");
  }
  
  my $ret = $record->SetFieldValue($field, $value);
  if($ret ne "") {
    logg(ERROR, "Can not set field $field to value $value!");
    logg(CQERROR, "$ret");
    return -1;
  }
  
  eval {
    $record->Validate();
  };
  if($@ ne "") {
    logg(ERROR, "Can not validate setting field $field to value $value!");
    logg(CQERROR, "$@\n");
    return -1;
  }
  
  eval {
    $record->Commit();
  };
  if($@ ne "") {
    logg(ERROR, "Can not commit setting field $field to value $value");
    logg(CQERROR, "$@\n");
    return -1;
  } else {
    logg(OK, "Commited change of field $field to value $value to database");
    return 1;
  }
}

#######################################
#  Change                             #
#  Change the state of a record and   #
#  modyfies a field.                  #
#  Inputs: a CQ session, a record,    #
#  a state_action to be performed,    #
#  a field and a value.               #
#  Returns 1 if change can be         #
#  commited, -1 on error.             #
#######################################

sub change {
  my $session      = shift @_;
  my $record       = shift @_;
  my $state_action = shift @_;
  my $field        = shift @_;
  my $field_value  = shift @_;
  my %fields;

  $fields{$field}=$field_value;

  # "Note_Entry" and "verified_in_release" are mandatory fields when setting a
  # DMS record to "Pass, these fields needs to be populated.
  # If a string is not submitted to the metheod then add default values
  if($state_action eq "Pass") {
    if(!$fields{"Note_Entry"}) {
      $fields{"Note_Entry"}="N/A";
    }
    if(!$fields{"verified_in_release"}) {
      $fields{"verified_in_release"}="N/A";
    }
  }

  my $mastership = is_master($record, $current_site);

  if($mastership == -1) {
    logg(ERROR, "Error while retreiving mastership status for site $current_site");
    return -1;
  }
  if(!$mastership) {
    logg(ERROR, "Does not have mastership to perform state actions on $record");
    return 0;
  }

  eval {
    $record->EditEntity($state_action);
  };
  if($@ ne "") {
    logg(ERROR, "Can not make record editable to $state_action");
    logg(CQERROR, "$@\n");
  }

  my $ret;
  foreach my $fl (keys %fields) {
    eval {
      $ret = $record->SetFieldValue($fl, $fields{$fl});
    };
    if($ret ne "") {
      logg(ERROR, "Can not set field $fl to value $fields{$fl}!");
      logg(CQERROR, "$ret\n");
      return -1;
    }
  }

  my $status;
  eval {
    $status = $record->Validate();
  };
  if(($@ ne "") && ($status ne "")) {
    logg(ERROR, "Can not validate setting record to $state_action!");
    logg(CQERROR, "$@, $status\n");
    return -1;
  }

  eval {
    $status = $record->Commit();
  };

  if(($@ ne "") && ($status ne "")) {
    $record->Revert();
    logg(ERROR, "Can not commit setting setting record to $state_action!");
    logg(CQERROR, "$@, $status \n");
    return -1;
  } else {
    logg(OK, "Commited setting record to $state_action!");
    return 1;
  }
}

#######################################
#  modify_issues                      #
#  Modifies "Official SW release"     #
#  field for a number of issues.      #
#  Takes a cq session object, a ref   #
#  to an issues array and a label as  #
#  input.                             #
#  Returns number of modified issues  #
#  or -1 on error.                    #
#######################################

sub modify_issues {
  my $session    = shift @_;
  my $issues_ref = shift @_;
  my $label      = shift @_;
  my $retval     = 0;

  #Check if the label is available for use.
  #I.e. it is registered in CMS
  if(label_is_valid($session, $label)) {
    logg(OK, "Updating issues for label $label");
  } else {
    logg(ERROR, "Label $label is not valid for this session on $current_site");
    return -1;
  }
  
  @issues = @{$issues_ref};
  my $ret;
  foreach my $issue (@issues) {
    $ret = modify_label($session, $issue, $label);
    if($ret == 1) {
      my $msg = "Modified issue $issue with label \"$label\"";
      print $msg, "\n";
      logg(OK, $msg);
    } else {
      logg(ERROR, "Could not modify issue $issue with label $label");
      $retval++;
    }
  }
  return $retval;
}

#######################################
#  change_state_issues                #
#  Changes the state for a number of  #
#  issues.                            #
#  Takes a cq session object, a ref   #
#  to an issues array and a           #
#  state_action and status as input.  #
#  Returns number of modified issues  #
#  or -1 on error.                    #
#######################################

sub change_state_issues {
  my $session      = shift @_;
  my $issues_ref   = shift @_;
  my $state_action = shift @_;
  my $status       = shift @_;
  my $retval       = 0;

  @issues = @{$issues_ref};
  my $ret;
  foreach my $issue (@issues) {
    $ret = change_state($session, $issue, $state_action, $status);
    if($ret == 1) {
      logg(OK, "Performed action $state_action on issue $issue");
    } else {
      logg(ERROR, "Could not perform action $state_action on issue $issue");
      $retval++;
    }
  }
  return $retval;
}

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
  
  
  # Build Query
  my $query = $session->BuildQuery(ISSUE_ENTITY);
  $query->BuildField(ID_FIELD);
  $query->BuildField(TITLE_FIELD);
  $query->BuildField(MASTERSHIP_FIELD);
  $query->BuildField(STATE_FIELD);
  $query->BuildField(INTEGRATED_STATUS_FIELD);
  $query->BuildField(VERIFIED_STATUS_FIELD);
  $query->BuildField(RELEASE_LABEL_FIELD);
  $query->BuildField(PROJ_ID);
  $query->BuildField(FIX_FOR_FIELD);

  my $filter_node = $query->BuildFilterOperator(CQ_OR);
  
  foreach my $issue(@{$issues_ref}) {
    $filter_node->BuildFilter(ID_FIELD, CQ_EQ, $issue);
  }
  return $query;
}


#######################################
#  logg                               #
#  Helper function for logging.       #
#  Takes error type string and error  #
#  message as input.                  #
#  Returns -1 of logging is off, 0 if #
#  logging was just turned off and 1  #
#  if logging is on.                  #
#######################################

sub logg {
  my $type = shift @_;
  my $message = shift @_;
  
  if(!$do_log) {return -1;}
  
  #If the log_handle is available
  #reuse it. If not open the file, in
  #append mode if it exists, otherwise
  #in write.
  if(!defined($log_handle)) {
    if(-f $log_file) {
      open($log_handle, ">>$log_file");
    } else {
      open($log_handle, ">$log_file");
    }
    if(!defined($log_handle)){
      print "Unable to open logfile $log_file. Logging is off.";
      $do_log = 0;
    } 
  }
  print $log_handle "$type ", create_time_stamp(), " $message\n";
  return $do_log;
}


#######################################
# site_exits                          #
# Helper function to check if a site  #
# is one of the valid sites that the  #
# script handles. Loggs a warning and #
# returns false if that is not the    #
# case, true if the site is ok.       #
#######################################

sub site_exists {
  my $site = shift @_;
  chomp $site;
  my @valid_sites = (SELD, JPTO, USSV, CNBJ);
  
  foreach my $valid_site (@valid_sites) {
    if($site eq $valid_site) {
      return 1;
    }
  }
  my $msg = "Site $site is not a valid site!";
  print $msg, "\n";
  logg(WARN, $msg);
  return 0;
}

#######################################
#  create_time_stamp                  #
#  Helper function to generate time   #
#  stamp strings for logging.         #
#  No input, returns time string.     #
#######################################'

sub create_time_stamp {
	#
	# creates timestamp file names
	#
  my @timedata = localtime(time);
  
	my $year = $timedata[5]+1900;
	
	#Prepend single digit in date or time with 0
	for(my $i = 0; $i<5; $i++) {
    $timedata[$i] =~ s/^(\d)$/0$1/;
  }

  $timedata[4]++;
  
	my $timeStamp = "$year.$timedata[4].$timedata[3]_$timedata[2].$timedata[1].$timedata[0]";
	return $timeStamp;
}

#######################################
#  usage                              #
#  Helper function that prints usage  #
#  string. No input, no return value. #
#######################################

sub usage {
  print "cqperl <script> -user <user> -pwd <password> -log <logfile> [-sites <site>[,...]] (-list [-unv <query> | -unl <query>] | -update -label <label>) (-query <query file> | -issues <issue[,...]>) -createlabel <labelproject>\n";
}


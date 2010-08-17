<?php
/*
<!--
#------------------------------------------------------------------
#  ____                      _____      _
# / ___|  ___  _ __  _   _  | ____|_ __(_) ___ ___ ___  ___  _ __
# \___ \ / _ \| '_ \| | | | |  _| | '__| |/ __/ __/ __|/ _ \| '_ \
#  ___) | (_) | | | | |_| | | |___| |  | | (__\__ \__ \ (_) | | | |
# |____/ \___/|_| |_|\__, | |_____|_|  |_|\___|___/___/\___/|_| |_|
#                    |___/
#
#------------------------------------------------------------------
# Sony Ericsson Mobile Communications, Tokyo, Japan
#------------------------------------------------------------------
#
# Prepared: David Pursehouse
# Approved:
# Checked :
#
# No.     :
# Date    : 2010-08-17 (YYYY-MM-DD)
# Rev.    :
# Location:
#
# Title   : check.php
#
#-----------------------------------------------------------------
-->
*/
?>
<!DOCTYPE html>
<html lang='en'>
    <head>
        <meta charset='utf-8' />
        <title>Android CM Web Server - Commit Message Checker</title>
        <link rel='stylesheet' href='style/style.css' type='text/css' />
    </head>

    <body>
        <div class='content'>
            <div style='float: left; width: 540px; margin: 20px 0;'>
                <h1 style="font-size: 1.2em; line-height: 100%; margin: 0; padding: 0 0 10px 0; border-bottom: 4px solid #eee;">
                    Commit Message Checker for Android Projects
                </h1>

                <div style="text-align: left; padding-top: 20px; clear: left; line-height: 100%;">
                <pre>
<?php
                $errors = 0;
                $warnings = 0;
                $MAX_TITLE_LENGTH = 70;
                $MAX_BODY_LENGTH = 70;

                function my_empty($val) {
                    $val = trim($val);
                    return empty($val) && $val !== 0;
                }

                // Check that a message has been entered
                $commit_message = $_POST['commit_message'];
                if ($commit_message == "") {
                    echo "ERR: Commit message is empty\n";
                    $errors ++;
                }
                else {
                    // Split the message into an array of lines
                    $message_array = explode("\n",$commit_message);
                    $num_lines = count($message_array);
                    echo("INF: Commit message contains $num_lines lines\n");

                    // Check that the commit message includes a message body
                    if ($num_lines == 1) {
                        echo("WRN: It is recommended not to make commit messages without a message body.\n");
                        $warnings ++;
                    }
                    else if ($num_lines >=2) {
                        // Check that the second line is blank
                        $line2 = $message_array[1];
                        if (!my_empty($line2)) {
                            echo("ERR: Line #1: Title must be followed by a blank line.\n");
                            $errors ++;
                        }
                    }

                    // Check the entire commit message to validate line length and DMS issues
                    for ($i=0; $i<$num_lines; $i++) {
                        // Keep track of how many errors were found so far, before starting to process this line
                        // and adjust the line count to index from 1 instead of 0, for user readability
                        $errors_so_far = $errors;
                        $index = $i+1;

                        // Length of the current line (adjusted for CR character that is counted)
                        $len = strlen($message_array[$i]) - 1;

                        // First line is the title.
                        if ($i ==0) {
                            // Check the length
                            if ($len > $MAX_TITLE_LENGTH) {
                                echo("ERR: Line #1: Title is too long (" .$len. " chars). Maximum length is " .$MAX_TITLE_LENGTH. " chars.\n");
                                $errors ++;
                            }

                            // Warn about DMS issues mentioned in the title
                            if (preg_match("/DMS(00)?([0-9]{6})/", $message_array[0])) {
                                echo("WRN: Line #1: It is recommended not to list DMS issues in the title.\n");
                                $warnings ++;
                            }
                        }
                        else {
                            // Check the length of the line
                            if ($len > $MAX_BODY_LENGTH) {
                                echo("ERR: Line #".$index.": Too long (" .$len. " chars). Maximum length is ".$MAX_BODY_LENGTH." chars.\n");
                                $errors ++;
                            }
                        }

                        // Check if there are any FIX= tags in the line
                        // At this point we don't care about upper/lower case or spaces
                        $fixcount = preg_match_all("/(FIX( )?=( )?)+/i", $message_array[$i], $matches);

                        // Check for multiple FIX= tags
                        if ($fixcount >= 2) {
                            echo("ERR: Line #".$index.": Too many FIX= tags.  Maximum is one per line.\n");
                            $errors ++;
                        }
                        else if ($fixcount ==1) {
                            // Check for malformed FIX= tags
                            for ($j=0; $j<$fixcount; $j++) {
                                // The tag must be all upper case
                                if (!preg_match("/([A-Z]){3}/", $matches[0][$j])) {
                                    echo("ERR: Line #".$index.": Invalid tag \"" .$matches[0][$j]. "\". Must be all upper-case.\n");
                                    $errors ++;
                                }

                                // The tag must not contain spaces
                                if (preg_match("/( )/", $matches[0][$j])) {
                                    echo("ERR: Line #".$index.": Invalid tag \"" .$matches[0][$j]. "\". Must not contain spaces.\n");
                                    $errors ++;
                                }
                            }
                        }

                        // If we found errors in this line, print the content of the line aswell
                        if ($errors > $errors_so_far) {
                            echo("     " .$message_array[$i]. "\n");
                        }
                    }
                }

                echo ("\n\n" .$errors. " error(s).\n" .$warnings. " warning(s).\n");
?>
                </pre>
                </div>

                <div style="text-align: justify; padding-top: 20px; clear: left;">
                    <a href="index.php">Back to the main page.</a>
                </div>
            </div>
        </div>
    </body>
</html>

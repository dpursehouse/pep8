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
# Title   : index.php
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

                <div style="text-align: justify; padding-top: 20px; clear: left;">
                    Enter your commit message in the text box below and press submit to verify it against the guideline.
                </div>

                <div style='float: left; width: 528px; margin-top: 30px;'>
                    <form action="check.php" method="POST">
                        <textarea tabindex='1' cols="85" rows="30" id="commit_message" name="commit_message"></textarea>
                        <input tabindex='2' align='left' type="submit" name="add_info" value="Submit"/>
                    </form>
                </div>

                <div style="text-align: justify; padding-top: 20px; clear: left;">
                    This page is maintained by ASW CM in Tokyo.   For support please write to <a href='mailto:DL-WW-eDream1_0-CM@sonyericsson.com'>DL-WW-eDream1_0-CM</a>.
                </div>

                <div style="text-align: justify; padding-top: 20px; clear: left;">
                    For further information about commit messages and other CM issues, please refer to the following pages:
                </div>

                <div style='float: left; width: 528px; margin-top: 30px;'>
                    <div style='float: left; font-size: 0.75em; border: 2px solid #ccc; padding: 10px; background-color: #f8f8f8; width: 460px;' class='curved'>
                        <div style='margin: 5px 0 0 5px;'>
                            &bull;&nbsp; <a href="http://androiki.sonyericsson.net/index.php5/Commit_messages">Commit message guideline</a><br />
                            &bull;&nbsp; <a href='http://androiki.sonyericsson.net/index.php5/EDream_CM'>Android CM wiki page</a><br />
                        </div>
                    </div>
                </div>

                <div style="text-align: justify; padding-top: 20px; clear: left;">
                    &nbsp;
                </div>
            </div>
        </div>
    </body>
</html>

��          |      �             !     2     E     _     x     �     �     �     �     �     �      K   )  �   u  M   �  �   M  >   �  g   '  �   �  \        t     �  2   �     	                                        
              bot_review_fails bot_review_success commit_subject_max_length email_username_not_match invalid_bot_action invalid_commit_message invalid_email_address issue_num_is_required milestone_is_required milestone_not_found milestone_release_note Project-Id-Version: PACKAGE VERSION
Report-Msgid-Bugs-To: 
PO-Revision-Date: YEAR-MO-DA HO:MI+ZONE
Last-Translator: FULL NAME <EMAIL@ADDRESS>
Language-Team: LANGUAGE <LL@li.org>
Language: en
MIME-Version: 1.0
Content-Type: text/plain; charset=UTF-8
Content-Transfer-Encoding: 8bit
 🙁 Review validation fails and approval has been revoked.
{error_message} 😊 Review validation success and approves the merge request.
* ✅ git username pass
* ✅ git email pass
* ✅ git commit message pass 🙁 The subject line must not exceed {commit_subject_max_length} characters. 🙁 Email username and address do not match. Please make sure that the username "{commit_author_name}" matches the email address "{commit_author_email}". 🙁 Invalid bot action, the correct action format is {action} 🙁 Invalid commit message subject '{commit_msg}', for examples:
{git_commit_subject_example_markdown} 🙁 Invalid email address "{commit_author_email}". must be from "@{gitlab_email_domain}" domain. Please provide a valid email address. Merge requests can only be merged if the source branch is associated with an existing issue. 🙁 Milestone is required. Milestone {milestone} not found 🙁 Milestone {milestone} release notes: 
{notes} 
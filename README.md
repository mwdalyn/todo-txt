# todo-txt
#### todos
Text-based task manager / Low-impact progress tracker.
#### meetings
Lightweight meeting note taker in simple .md/.txt format.


### What
#### todos
Auto-opens a daily todo file on unlock. 
Removes or carries tasks as they are completed DoD.
Facilitates categorization, recurring tasks (habits), priority task flagging. 
#### meetings
Win+R > "meeting" trigger to begin taking notes.
Scaffolding for future Google Calendar integration to help organize things, in conjunction with a Google Calendar-Jira workflow.
Ultimte goal: Organizing meeting notes by Jira ticket.

### Why
Inspired by fatigue over various task managers (account creation, sync) and note takers (disorganized, detached), plus a desire to centralize. 

### Future
Database creation and maintenance.
Tagging tasks for cross-category filtering or management.
Jira integration (ticket updates by category or by task, other).
Google Calendar integration for both meetings and todos.


> [!IMPORTANT] For meetings trigger, create "mtg.bat" file in 'meetings\winr\' subdirectory and attach its location to PATH.
Add the following to mtg.bat: 
```
@echo off
pythonw "C:\path\to\meetings.py"
```
>This will allow use of Win+R > "mtg" trigger.**
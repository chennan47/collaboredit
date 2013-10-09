===================
 Code Review Notes
===================

Files
-----

* Missing requirements.txt
* Make paths to static files dynamic


Python
------

* Remove unused imports
* PEP8 compliance
* functions should have docstrings
* Remove User.cursor, as it is not used

Javascript
----------

* Move JS to an external file
* remove commented code
* cyclers should be combined into a single function, named based on its action
* rename mouseOver() to bindMouseOverHandlers()
* rename tagCheck() to ensureNameTagIsPresent()
* etc.
* All code should be moved to a document.onload handler
* remove body's onload= attribute
"""Pure policy: category routing, the triage score, statutory deadlines, photo integrity.

Nothing in this package touches a database, a network, a clock it was not handed,
or a request. That is the point of it being separate — these are the rules a
citizen or an officer may want to argue with, so they have to be readable and
testable on their own, without a server running.
"""

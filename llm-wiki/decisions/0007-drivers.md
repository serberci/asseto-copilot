# 0007 — A driver token is not the host token

The host token creates the administrator password in `data/admin.password` the first time the database has no administrator. A person logs into the dashboard with a name and a password. The Windows agent does not accept that password. The driver generates an agent token on Account. The page shows it once, and the host stores only a hash. A later visit cannot reveal it. Generating another token replaces the hash, and the agent must be given the new value.

A driver sees only their sessions. Asking for another driver's session or lap returns 404. The other driver's fastest valid lap on the same game, track, and car is still used as a comparison, with the same entry-speed rule as a personal reference. The compared lap is named. It is not a copy of their token or their session list.

Laps recorded with the host token stay unassigned. The administrator can attach those sessions to one driver, or give a single lap to a driver from the lap list. Revoking a driver stops the login and leaves the laps in place, so older comparisons still have a name. Deleting a driver removes the account and makes those laps unassigned. The telemetry stays.

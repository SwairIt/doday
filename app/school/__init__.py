"""School portal integration — pluggable provider scaffold.

Two providers are sketched: 'school_mo' (Школьный портал МО, school.mosreg.ru)
and 'mesh' (МЭШ, dnevnik.mos.ru). Until a real auth_token is configured, sync()
returns a clear "credentials needed" error explaining what to put in .env.
"""

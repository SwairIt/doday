"""Admin panel + user-submitted complaints.

Admins (users with users.is_admin=True) can access /doday/app/root и /api/admin/*.
Read-only complaints API also accepts ADMIN_TOKEN header (for me / Claude
to fetch via curl when юзер просит «посмотри жалобы за сегодня»).
"""

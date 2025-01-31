# migrations/1.0/pre-migration.py
def migrate(cr, version):
    # Menambahkan kolom accurate_vendor_code
    cr.execute("""
        ALTER TABLE res_partner
        ADD COLUMN IF NOT EXISTS accurate_vendor_code varchar;
    """)
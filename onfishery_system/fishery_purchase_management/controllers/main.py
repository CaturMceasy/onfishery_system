from odoo import http
from odoo.http import request
import zipfile
import io
import base64

class AccurateExportController(http.Controller):
    @http.route('/web/binary/download_multiple_attachments', type='http', auth="user")
    def download_multiple_attachments(self, attachment_ids, **kw):
        attachment_ids = [int(x) for x in attachment_ids.split(',')]
        attachments = request.env['ir.attachment'].browse(attachment_ids)

        # Jika hanya 1 file, langsung download
        if len(attachments) == 1:
            attachment = attachments[0]
            return request.make_response(
                base64.b64decode(attachment.datas),
                headers=[
                    ('Content-Type', 'application/xml'),
                    ('Content-Disposition', f'attachment; filename="{attachment.name}"')
                ]
            )

        # Jika lebih dari 1 file, buat zip
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w') as zf:
            for attachment in attachments:
                zf.writestr(attachment.name, base64.b64decode(attachment.datas))

        memory_file.seek(0)
        return request.make_response(
            memory_file.read(),
            headers=[
                ('Content-Type', 'application/zip'),
                ('Content-Disposition', f'attachment; filename="accurate_export_{http.datetime.now():%Y%m%d_%H%M%S}.zip"')
            ]
        )
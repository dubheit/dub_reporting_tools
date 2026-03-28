import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class DocumentsDocument(models.Model):
    _inherit = 'documents.document'

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to embed ILovePDF action on new folders."""
        records = super().create(vals_list)

        # Embed ILovePDF action on newly created folders
        new_folders = records.filtered(lambda r: r.type == 'folder')
        if new_folders:
            self._embed_ilovepdf_action_on_folders(new_folders)

        return records

    @api.model
    def _embed_ilovepdf_action_on_folders(self, folders):
        """Embed ILovePDF server action on the given folders."""
        try:
            server_action = self.env.ref(
                'dub_reporting_ilovepdf_documents.ir_actions_server_ilovepdf_process',
                raise_if_not_found=False
            )
            if not server_action:
                _logger.warning('ILovePDF server action not found, skipping embedding')
                return

            for folder in folders:
                try:
                    self.action_folder_embed_action(folder.id, server_action.id)
                    _logger.info('Embedded ILovePDF action on folder: %s (ID: %d)', folder.name, folder.id)
                except Exception as e:
                    _logger.warning('Failed to embed ILovePDF action on folder %s: %s', folder.name, e)
        except Exception as e:
            _logger.error('Error embedding ILovePDF action: %s', e)

    @api.model
    def _embed_ilovepdf_action_on_all_folders(self):
        """Embed ILovePDF action on all existing folders. Called by post_init_hook."""
        folders = self.search([('type', '=', 'folder')])
        if folders:
            _logger.info('Embedding ILovePDF action on %d existing folders', len(folders))
            self._embed_ilovepdf_action_on_folders(folders)

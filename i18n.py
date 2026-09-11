"""Minimal hand-rolled i18n: a flat cs/en string table plus a `make_t`
helper. No framework - this app has no build step and only two languages,
so a dict beats pulling in gettext/babel.
"""
import json

DEFAULT_LANG = "cs"
SUPPORTED_LANGS = ("cs", "en")

TRANSLATIONS = {
    "cs": {
        "brand": "Client of AnnoPage Client",

        "nav.new_job": "Nová úloha",
        "nav.history": "Historie",
        "nav.settings": "Nastavení",

        "common.select_placeholder": "-- vyberte --",
        "common.default_placeholder": "-- výchozí --",
        "common.none_placeholder": "-- žádný --",
        "common.default": "výchozí",
        "common.none": "žádný",
        "common.delete": "smazat",
        "common.detail": "detail",
        "common.created_at": "Vytvořeno",
        "common.captioning_profile": "Captioning profil",
        "common.input": "Vstup",
        "common.state": "Stav",

        "new_job.title": "Nová úloha",
        "new_job.no_target_pre": "Nemáte žádný uložený target.",
        "new_job.no_target_link": "Přidejte ho v nastavení",
        "new_job.no_target_post": "předtím, než spustíte úlohu.",
        "new_job.input_folder_legend": "Vstupní složka",
        "new_job.input_folder_label": 'Cesta ke složce s podsložkami <code>images/</code>, volitelně <code>alto_xmls/</code> a <code>metadata.json</code>',
        "new_job.inspect_btn": "Ověřit obsah",
        "new_job.target_legend": "Target",
        "new_job.target_label": "Cílová instance",
        "new_job.engine_label": "Engine (nepovinné, jinak výchozí)",
        "new_job.outputs_legend": "Výstupy",
        "new_job.output_captioning_prompts": "Captioning prompty",
        "new_job.captioning_profile_legend": "Captioning profil (nepovinné)",
        "new_job.output_folder_legend": "Výstupní složka (nepovinné)",
        "new_job.output_folder_label": "Necháte-li prázdné, výstup se uloží do vlastního úložiště appky.",
        "new_job.submit_btn": "Spustit úlohu",
        "new_job.checking": "Ověřuji...",
        "new_job.images_word": "obrázků",
        "new_job.files_word": "souborů",
        "new_job.records_word": "záznamů",
        "new_job.no_alto": ", bez ALTO",
        "new_job.no_metadata": ", bez metadata.json",
        "new_job.pick_from_prefix": "-- vybrat z",
        "new_job.img_abbrev": "obr.",
        "new_job.cannot_load_engine": "Nelze načíst engine",
        "new_job.job_start_failed": "Nepodařilo se spustit úlohu",

        "jobs.title": "Historie úloh",
        "jobs.empty": "Zatím žádné úlohy.",

        "job_detail.title_prefix": "Úloha",
        "job_detail.created_at_colon": "Vytvořeno:",
        "job_detail.target_colon": "Target:",
        "job_detail.input_colon": "Vstup:",
        "job_detail.output_colon": "Výstup:",
        "job_detail.state_colon": "Stav:",
        "job_detail.download": "Stáhnout výstup (zip)",
        "job_detail.log_summary": "Log (posledních 5 řádků)",

        "settings.title": "Nastavení",
        "settings.targets_heading": "Targety",
        "settings.api_key_header": "API klíč",
        "settings.target_label_placeholder": "Label, např. 'lokální'",
        "settings.api_key_placeholder": "API klíč",
        "settings.add_target_btn": "Přidat target",
        "settings.profiles_heading": "Captioning profily",
        "settings.profile_label_placeholder": "Label, např. 'gpt-4.1-mini'",
        "settings.profile_settings_placeholder": "Obsah IMAGE_CAPTIONING_SETTINGS.json",
        "settings.add_profile_btn": "Přidat profil",
        "settings.engines_heading": "Registrované enginy",
        "settings.engines_notice": (
            "Toto je lokální záznam toho, co zaregistroval <code>scripts/register_engine.py</code> — "
            "DocAPI samo o sobě neumí obsah enginu zpětně vrátit (ani administrátorům), takže tohle "
            "nemusí odpovídat úplně všem enginům na daném targetu, jen těm zaregistrovaným odsud."
        ),
        "settings.engines_empty": "Zatím žádný engine nebyl přes tento skript zaregistrován.",
        "settings.registered_at_prefix": "zaregistrováno",
        "settings.invalid_json": "Settings musí být validní JSON.",
        "settings.add_target_failed": "Nepodařilo se přidat target",
        "settings.add_profile_failed": "Nepodařilo se přidat profil",

        "errors.path_empty": "Cesta nesmí být prázdná.",
        "errors.folder_not_found": "Složka neexistuje: {path}",
        "errors.missing_images_subfolder": "Chybí podsložka 'images'.",
        "errors.no_images_in_folder": "Ve složce 'images' nejsou žádné obrázky.",
        "errors.metadata_load_failed": "metadata.json se nepodařilo načíst: {exc}",
        "errors.job_not_found": "Job nenalezen.",
        "errors.target_fields_required": "label, api_url a api_key jsou povinné.",
        "errors.target_not_found": "Target nenalezen.",
        "errors.select_valid_target": "Vyberte platný target.",
        "errors.profile_fields_required": "label a settings (JSON objekt) jsou povinné.",
        "errors.profile_not_found": "Profil nenalezen.",
        "errors.invalid_input_folder": "Neplatná vstupní složka.",
        "errors.captioning_profile_not_found": "Zvolený captioning profil neexistuje.",
        "errors.job_not_finished": "Job ještě neskončil.",
    },
    "en": {
        "brand": "Client of AnnoPage Client",

        "nav.new_job": "New job",
        "nav.history": "History",
        "nav.settings": "Settings",

        "common.select_placeholder": "-- select --",
        "common.default_placeholder": "-- default --",
        "common.none_placeholder": "-- none --",
        "common.default": "default",
        "common.none": "none",
        "common.delete": "delete",
        "common.detail": "detail",
        "common.created_at": "Created",
        "common.captioning_profile": "Captioning profile",
        "common.input": "Input",
        "common.state": "State",

        "new_job.title": "New job",
        "new_job.no_target_pre": "You don't have any saved target.",
        "new_job.no_target_link": "Add one in settings",
        "new_job.no_target_post": "before running a job.",
        "new_job.input_folder_legend": "Input folder",
        "new_job.input_folder_label": 'Path to a folder with subfolders <code>images/</code>, optionally <code>alto_xmls/</code> and <code>metadata.json</code>',
        "new_job.inspect_btn": "Check contents",
        "new_job.target_legend": "Target",
        "new_job.target_label": "Target instance",
        "new_job.engine_label": "Engine (optional, otherwise default)",
        "new_job.outputs_legend": "Outputs",
        "new_job.output_captioning_prompts": "Captioning prompts",
        "new_job.captioning_profile_legend": "Captioning profile (optional)",
        "new_job.output_folder_legend": "Output folder (optional)",
        "new_job.output_folder_label": "If left empty, output is stored in the app's own storage.",
        "new_job.submit_btn": "Start job",
        "new_job.checking": "Checking...",
        "new_job.images_word": "images",
        "new_job.files_word": "files",
        "new_job.records_word": "records",
        "new_job.no_alto": ", no ALTO",
        "new_job.no_metadata": ", no metadata.json",
        "new_job.pick_from_prefix": "-- pick from",
        "new_job.img_abbrev": "img.",
        "new_job.cannot_load_engine": "Could not load engine",
        "new_job.job_start_failed": "Failed to start job",

        "jobs.title": "Job history",
        "jobs.empty": "No jobs yet.",

        "job_detail.title_prefix": "Job",
        "job_detail.created_at_colon": "Created:",
        "job_detail.target_colon": "Target:",
        "job_detail.input_colon": "Input:",
        "job_detail.output_colon": "Output:",
        "job_detail.state_colon": "State:",
        "job_detail.download": "Download output (zip)",
        "job_detail.log_summary": "Log (last 5 lines)",

        "settings.title": "Settings",
        "settings.targets_heading": "Targets",
        "settings.api_key_header": "API key",
        "settings.target_label_placeholder": "Label, e.g. 'local'",
        "settings.api_key_placeholder": "API key",
        "settings.add_target_btn": "Add target",
        "settings.profiles_heading": "Captioning profiles",
        "settings.profile_label_placeholder": "Label, e.g. 'gpt-4.1-mini'",
        "settings.profile_settings_placeholder": "Contents of IMAGE_CAPTIONING_SETTINGS.json",
        "settings.add_profile_btn": "Add profile",
        "settings.engines_heading": "Registered engines",
        "settings.engines_notice": (
            "This is a local record of what <code>scripts/register_engine.py</code> registered — "
            "DocAPI itself cannot report an engine's contents back (not even to admins), so this "
            "may not match every engine on a given target, only the ones registered from here."
        ),
        "settings.engines_empty": "No engine has been registered through this script yet.",
        "settings.registered_at_prefix": "registered",
        "settings.invalid_json": "Settings must be valid JSON.",
        "settings.add_target_failed": "Failed to add target",
        "settings.add_profile_failed": "Failed to add profile",

        "errors.path_empty": "Path must not be empty.",
        "errors.folder_not_found": "Folder does not exist: {path}",
        "errors.missing_images_subfolder": "Missing 'images' subfolder.",
        "errors.no_images_in_folder": "No images found in the 'images' folder.",
        "errors.metadata_load_failed": "Failed to load metadata.json: {exc}",
        "errors.job_not_found": "Job not found.",
        "errors.target_fields_required": "label, api_url and api_key are required.",
        "errors.target_not_found": "Target not found.",
        "errors.select_valid_target": "Select a valid target.",
        "errors.profile_fields_required": "label and settings (JSON object) are required.",
        "errors.profile_not_found": "Profile not found.",
        "errors.invalid_input_folder": "Invalid input folder.",
        "errors.captioning_profile_not_found": "The selected captioning profile does not exist.",
        "errors.job_not_finished": "Job has not finished yet.",
    },
}


def normalize_lang(lang: str | None) -> str:
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def get_translations(lang: str | None) -> dict:
    return TRANSLATIONS[normalize_lang(lang)]


def make_t(lang: str | None):
    translations = get_translations(lang)

    def t(key: str) -> str:
        return translations.get(key, key)

    return t


def translations_json(lang: str | None) -> str:
    return json.dumps(get_translations(lang), ensure_ascii=False)

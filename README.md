# robotist-console

Deploy mirror for the Robotist operator console (Flask: `/manage/` CMS + `/grn/` admin).

Source of truth: `lareesahu/robotist-ecommerce` (private). This repo exists only so the
console can be built and served on a Render account without access to the private repo.
Do not edit here — changes land in the private repo and get re-mirrored.

Render: `pip install -r catalog/requirements.txt`, start `gunicorn 'catalog.app:create_app()'`.

"""
One-time migration: move every image stored in the database to Cloudinary.

What it moves
    site_photos     website photos (hero, destinations, gallery, ...)   -> cloud_media pointer
    site_packages   the photo on each homepage package card             -> cloud_media pointer
    hotel_images    base64 hotel photos -> replaced by https:// URLs inside images_json

Safe to re-run: anything already on Cloudinary is skipped.

Usage (from the project root, with DATABASE_URL and CLOUDINARY_* set, e.g. in .env):
    python -m scripts.migrate_images_to_cloudinary --dry-run     # just report what would happen
    python -m scripts.migrate_images_to_cloudinary               # upload; keep DB copies as a backup
    python -m scripts.migrate_images_to_cloudinary --purge-db    # also empty the image bytes in the DB

Before touching hotel_images the script saves the old values to
migration_backup_hotel_images.json, so nothing is ever lost.
"""
import argparse
import json
import sys

from backend.app import create_app
from backend.config import Config
from backend.extensions import db
from backend.models import CloudMedia, HotelImages, SitePackage, SitePhoto
from backend.services import cloud_media


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only, change nothing")
    ap.add_argument("--purge-db", action="store_true",
                    help="after a successful upload, empty the image bytes stored in the database")
    args = ap.parse_args()

    app = create_app()
    with app.app_context():
        if not cloud_media.configured():
            sys.exit("Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY and "
                     "CLOUDINARY_API_SECRET (or CLOUDINARY_URL) first.")
        db.create_all()   # makes sure the cloud_media table exists
        done = skipped = failed = 0

        # ---- website photos -------------------------------------------------
        for row in db.session.query(SitePhoto).all():
            have_cloud = cloud_media.get("site_photo", row.slot) is not None
            data = bytes(row.data) if row.data else b""
            try:
                if not data:
                    skipped += 1
                    continue
                if not have_cloud:
                    print(f"site photo  {row.slot:<22} {len(data)//1024:>6} KB -> Cloudinary")
                    if not args.dry_run:
                        cloud_media.save("site_photo", row.slot, data)
                        done += 1
                else:
                    skipped += 1
                if args.purge_db and not args.dry_run:
                    row.data = b""
                if not args.dry_run:
                    db.session.commit()
            except Exception as exc:
                db.session.rollback()
                failed += 1
                print(f"  FAILED {row.slot}: {exc}")

        # ---- package photos -------------------------------------------------
        for pkg in db.session.query(SitePackage).all():
            data = bytes(pkg.photo_data) if pkg.photo_data else b""
            if not data:
                skipped += 1
                continue
            try:
                if cloud_media.get("package", pkg.id) is None:
                    print(f"package     #{pkg.id:<21} {len(data)//1024:>6} KB -> Cloudinary")
                    if not args.dry_run:
                        cloud_media.save("package", pkg.id, data)
                        done += 1
                else:
                    skipped += 1
                if args.purge_db and not args.dry_run:
                    pkg.photo_data = None
                if not args.dry_run:
                    db.session.commit()
            except Exception as exc:
                db.session.rollback()
                failed += 1
                print(f"  FAILED package {pkg.id}: {exc}")

        # ---- hotel photos ---------------------------------------------------
        backup = {}
        for row in ([] if not Config.CLOUDINARY_HOTEL_PHOTOS else HotelImages.query.all()):
            try:
                images = json.loads(row.images_json)
            except ValueError:
                continue
            if not isinstance(images, list) or not any(
                    isinstance(i, str) and i.startswith("data:image/") for i in images):
                continue
            backup[row.hotel_id] = images
            print(f"hotel       {row.hotel_id:<22} {sum(1 for i in images if str(i).startswith('data:'))} photo(s) -> Cloudinary")
            if args.dry_run:
                continue
            try:
                new_images = [cloud_media.hotel_data_url_to_cloud(i, row.hotel_id) for i in images]
                with open("migration_backup_hotel_images.json", "w", encoding="utf-8") as fh:
                    json.dump(backup, fh)
                row.images_json = json.dumps(new_images)
                db.session.commit()
                done += 1
            except Exception as exc:
                db.session.rollback()
                failed += 1
                print(f"  FAILED hotel {row.hotel_id}: {exc}")

        label = "would upload" if args.dry_run else "uploaded"
        print(f"\nDone. {label}: {done if not args.dry_run else '(see list above)'}, "
              f"already on Cloudinary / nothing to do: {skipped}, failed: {failed}")
        if failed:
            sys.exit(1)


if __name__ == "__main__":
    main()

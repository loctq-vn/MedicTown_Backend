from app.services.notification_service import delete_stale_device_tokens


if __name__ == "__main__":
    deleted_count = delete_stale_device_tokens(max_age_days=90)
    print(f"Deleted {deleted_count} stale device tokens")
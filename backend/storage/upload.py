"""Storage upload helpers."""

def upload_file(path: str, bucket: str):
    return {"path": path, "bucket": bucket, "uploaded": False}

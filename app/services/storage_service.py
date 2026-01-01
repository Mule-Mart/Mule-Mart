from flask import current_app
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
import os
from botocore.exceptions import ClientError


PROFILE_IMAGES_FOLDER = "profile_images"
ITEM_IMAGES_FOLDER = "item_images"

ALLOWED_IMAGE_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
    "image/gif": "gif",
}


def is_mimetype_allowed(mimetype: str) -> bool:
    """
    Check if the uploaded image's MIME type (Content-Type) is allowed.

    Params
    ------
    mimetype: str
        The MIME type of the uploaded image.

    Returns
    -------
    bool
        `True` if `content_type` is a supported MIME type. Otherwise, returns `False`.
    """
    return mimetype in ALLOWED_IMAGE_TYPES


def mimetype_to_extension(mimetype) -> str:
    """
    Converts a given MIME type to the corresponding file extension (e.g. `image/jpeg` --> `jpg`)
    """
    return ALLOWED_IMAGE_TYPES[mimetype]


def generate_unique_filename(
    original_filename: str, folder: str, content_type: str | None = None
) -> str:
    """
    Generates a secure, unique filename and prepends a folder path.
    Enforces the correct extension if `content_type` is provided.

    Params
    ------
    original_filename: str
        The original name of the file.

    folder: str
        The folder path to prepend to the filename.

    content_type: str, optional
        The MIME type of the file. If provided, ensures the filename has the correct extension.

    Returns
    -------
    str
        The unique filename including the folder path.

    """
    filename = secure_filename(original_filename)

    if content_type and is_mimetype_allowed(content_type):
        extension = mimetype_to_extension(content_type)
        filename_without_extension = os.path.splitext(filename)[0]
        filename = f"{filename_without_extension}.{extension}"

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    unique_name = f"{timestamp}_{filename}"
    return os.path.join(folder, unique_name)


def generate_put_url(filename: str, content_type: str) -> str | None:
    """
    Helper method for generating the presigned PUT url for uploading a given image to the app's default storage bucket

    Params
    ------
    filename: str
        The name of the file to be uploaded including the full path from the bucket root.

    content_type: str
        The MIME type of the file.

    Returns
    -------
    str | None
        The generated presigned PUT URL for uploading a file with the given filename and content type to the app's default storage bucket.
    """
    try:
        put_url = current_app.s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": current_app.s3_bucket_id,
                "Key": filename,
                "ContentType": content_type,
            },
            ExpiresIn=3600,
        )
        return put_url
    except Exception as e:
        current_app.logger.exception("Error generating presigned URL")
        return None


def generate_get_url(filename: str)-> str | None:
    """
    Generates a presigned GET url for downloading a given image file from the app's default storage bucket.
    Does not verify existence of the file for which the URL is being generated.

    Params
    ------
    filename: str
        The name of the file to be downloaded including the full path from the bucket root.
    
    Returns
    -------
    str | None
        The generated presigned GET URL for downloading the file. `None` if the URL was not successfully generated
    """
    try:
        get_url = current_app.s3_client.generate_presigned_url(
            "get_object", 
            Params={
                "Key": filename,
                "Bucket": current_app.s3_bucket_id,
            },
            ExpiresIn=3600,
        )
        return get_url
    except Exception:
        current_app.logger.exception("Error generating presigned GET URL")
        return None



def delete_file(filename: str) -> bool:
    """
    Helper method for deleting a given file from the app's default storage bucket.
    No change occurs if the file does not exist.

    Params
    ------
    filename: str
        The name of the file to be deleted including the full path from the bucket root.

    Returns
    -------
    bool
        `True` if the file was successfully deleted and no errors were raised. Otherwise, returns `False`.
    """
    try:
        current_app.s3_client.delete_object(
            Bucket=current_app.s3_bucket_id, Key=filename
        )
        return True
    except Exception as e:
        current_app.logger.exception(f"Error deleting file `{filename}`")
        return False


def file_exists(filename: str) -> bool:
    """
    Helper method for checking if the file with the given filename exists in the app's default storage bucket.

    Params
    ------
    filename: str
        The name of the file whose existence is being checked including the full path from the bucket root.

    Returns
    -------
    bool
        `True` if the file exists in the storage bucket. Otherwise, `False`
    """
    try:
        current_app.s3_client.head_object(Bucket=current_app.s3_bucket_id, Key=filename)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        else:
            raise e
    except Exception as e:
        current_app.logger.exception(f"Error verifying existence of file `{filename}`")
        raise e


def validate_profile_image_upload(
    new_profile_image: str, old_profile_image: str | None
) -> tuple[bool, str | None]:
    """
    Validates profile image uploads by ensuring:
     - the new profile image has the right file path (prefix)
     - the new profile image is different from the current profile image
     - the new profile image exists in the app's default storage bucket

     Params
     ------
     new_profile_image: str
        The filename to be set as the user's new profile image including the full path from the bucket root.

    current_profile_image: str | None
        The filename of the user's current profile image if any.

    Returns
    -------
    is_valid: bool
        `True` if the profile image upload is valid. Otherwise, returns `False`
    error_message: str | None
        Error message detailing why the profile image upload is not valid if not valid. `None` if the profile image upload is valid.
    """
    if not new_profile_image.startswith(f"{PROFILE_IMAGES_FOLDER}/"):
        error_message = f"Invalid profile image path: `{new_profile_image}`"
        return False, error_message

    if new_profile_image == old_profile_image:
        error_message = f"New profile image `{new_profile_image}` must be different from current profile image `{old_profile_image}`"
        return False, error_message

    if not file_exists(new_profile_image):
        error_message = f"New profile image file `{new_profile_image}` does not exist"
        return False, error_message

    return True, None


def validate_item_image_upload(item_image: str) -> tuple[bool, str | None]:
    """
    Validates item image uploads by ensuring:
     - the item image file has the right file path (prefix)
     - the item image file exists in the app's default storage bucket

    Params
    ------
    item_image: str
        The filename of the item image including the full path from the bucket root.

    Returns
    -------
    is_valid: bool
        `True` if item image was found to be valid. Otherwise, returns `False`.
    error_message: str | None
        Error message detailing why the item image is invalid.
    """
    if not item_image.startswith(f"{ITEM_IMAGES_FOLDER}/"):
        error_message = f"Invalid item image path: `{item_image}`"
        return False, error_message
    if not file_exists(filename=item_image):
        error_message = f"Item image file `{item_image}` does not exist"
        return False, error_message

    return True, None

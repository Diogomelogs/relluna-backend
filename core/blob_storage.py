import os
import uuid
from azure.storage.blob import BlobServiceClient
from fastapi import UploadFile


async def upload_file_to_blob(file: UploadFile, user_id: str) -> str:
    """
    Upload para Azure Blob e retorna URL pública.
    """
    connection_string = os.getenv("AZURE_BLOB_CONNECTION_STRING")
    container_name = os.getenv("AZURE_BLOB_CONTAINER", "memories")

    if not connection_string:
        raise RuntimeError("AZURE_BLOB_CONNECTION_STRING não definido.")

    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(container_name)

    original = file.filename or "file"
    ext = ""
    if "." in original:
        ext = "." + original.split(".")[-1].lower()

    blob_name = f"{user_id}_{uuid.uuid4()}{ext}"

    data = await file.read()
    blob_client = container_client.get_blob_client(blob_name)
    blob_client.upload_blob(data, overwrite=True)

    account_name = blob_client.account_name
    url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_name}"
    return url

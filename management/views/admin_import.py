import os
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.utils.text import get_valid_filename

from management.management.commands.import_cora_xlsx import run_cora_import


MAX_UPLOAD_MB = 25


def admin_import_excel_view(request):
    if request.method != "POST":
        return JsonResponse({"status": "failed", "message": "Invalid method."}, status=405)

    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"status": "failed", "message": "No file uploaded."}, status=400)

    if not upload.name.lower().endswith(".xlsx"):
        return JsonResponse({"status": "failed", "message": "Only .xlsx files are supported."}, status=400)

    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if upload.size and upload.size > max_bytes:
        return JsonResponse(
            {
                "status": "failed",
                "message": f"File too large. Max {MAX_UPLOAD_MB}MB.",
            },
            status=400,
        )

    uploads_dir = os.path.join(settings.BASE_DIR, "uploads", "imports")
    os.makedirs(uploads_dir, exist_ok=True)

    base_name = get_valid_filename(os.path.splitext(upload.name)[0]) or "import"
    file_name = f"{base_name}-{uuid.uuid4().hex}.xlsx"
    file_path = os.path.join(uploads_dir, file_name)

    with open(file_path, "wb") as target:
        for chunk in upload.chunks():
            target.write(chunk)

    clear_requested = str(request.POST.get("clear_existing", "")).lower() in {
        "true",
        "1",
        "yes",
        "on",
    }
    confirm_clear = str(request.POST.get("confirm_clear", "")).lower() in {
        "true",
        "1",
        "yes",
        "on",
    }
    if clear_requested and not confirm_clear:
        return JsonResponse(
            {
                "status": "failed",
                "message": "Please confirm clearing existing data.",
            },
            status=400,
        )

    try:
        result = run_cora_import(
            file_path,
            source_file=upload.name,
            report_date="",
            debug=str(request.POST.get("debug", "")).lower() in {"1", "true", "yes"},
            clear=clear_requested,
            stdout=None,
        )
    except Exception as exc:
        return JsonResponse(
            {
                "status": "failed",
                "message": "Import failed. Please check the file and try again.",
                "errors": [{"sheet": "", "error": str(exc)}],
            }
        )

    summary = result.get("summary", [])
    errors = result.get("errors", [])

    status = result.get("status", "success")
    if status == "success":
        message = "Import completed successfully."
    elif status == "partial":
        message = "Import completed with warnings. Review the summary."
    else:
        message = "Import failed. Please review the summary."

    return JsonResponse(
        {
            "status": status,
            "message": message,
            "report_id": result.get("report_id"),
            "borrower_id": result.get("borrower_id"),
            "summary": summary,
            "errors": errors,
            "total_imported": result.get("total_imported", 0),
            "total_skipped": result.get("total_skipped", 0),
        }
    )

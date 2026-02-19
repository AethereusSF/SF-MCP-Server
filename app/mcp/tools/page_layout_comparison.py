"""
Page Layout Comparison Tool for Salesforce MCP Server

Fetches page layout XML from source and target orgs via Metadata API,
compares sections, fields, and related lists, and writes a CSV diff report.

Created by Sameer
"""
import base64
import csv
import io
import json
import logging
import os
import time
import zipfile
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from lxml import etree

from app.mcp.server import register_tool
from app.services.salesforce import get_salesforce_connection
from app.mcp.tools.oauth_auth import get_stored_tokens
from app.mcp.tools.utils import format_error_response, format_success_response

logger = logging.getLogger(__name__)

METADATA_NS = "http://soap.sforce.com/2006/04/metadata"

# ─────────────────────────────────────────────────────────────────────────────
# ORG CREDENTIAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_org_credentials(user_id: Optional[str]) -> Tuple[str, str, str]:
    """
    Return (instance_url, access_token, api_version) for the given org.
    If user_id is None, falls back to the currently active/default org.
    """
    # Resolve API version — try config, fall back to "59.0"
    try:
        from app.config import get_config
        api_version = str(get_config().salesforce_api_version)
    except Exception:
        api_version = "59.0"

    if user_id is None:
        sf = get_salesforce_connection()
        instance_url = f"https://{sf.sf_instance}"
        return instance_url, sf.session_id, api_version

    tokens = get_stored_tokens()
    if user_id not in tokens:
        raise ValueError(
            f"No active session found for org user_id='{user_id}'. "
            "Run list_connected_orgs to see connected orgs, then login first."
        )
    t = tokens[user_id]
    return t["instance_url"], t["access_token"], api_version


# ─────────────────────────────────────────────────────────────────────────────
# METADATA API RETRIEVE  (batched — one call for all layouts)
# ─────────────────────────────────────────────────────────────────────────────

def _build_retrieve_envelope(token: str, api_version: str,
                              layout_names: List[str]) -> bytes:
    members_xml = "\n                        ".join(
        f"<met:members>{n}</met:members>" for n in layout_names
    )
    soap = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:met="{METADATA_NS}">
    <soapenv:Header>
        <met:CallOptions><met:client>SF-MCP-PageLayout</met:client></met:CallOptions>
        <met:SessionHeader><met:sessionId>{token}</met:sessionId></met:SessionHeader>
    </soapenv:Header>
    <soapenv:Body>
        <met:retrieve>
            <met:retrieveRequest>
                <met:apiVersion>{api_version}</met:apiVersion>
                <met:unpackaged>
                    <met:types>
                        {members_xml}
                        <met:name>Layout</met:name>
                    </met:types>
                    <met:version>{api_version}</met:version>
                </met:unpackaged>
            </met:retrieveRequest>
        </met:retrieve>
    </soapenv:Body>
</soapenv:Envelope>"""
    return soap.encode("utf-8")


def _build_status_envelope(token: str, api_version: str,
                            retrieve_id: str) -> bytes:
    soap = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:met="{METADATA_NS}">
    <soapenv:Header>
        <met:SessionHeader><met:sessionId>{token}</met:sessionId></met:SessionHeader>
    </soapenv:Header>
    <soapenv:Body>
        <met:checkRetrieveStatus>
            <met:asyncProcessId>{retrieve_id}</met:asyncProcessId>
            <met:includeZip>true</met:includeZip>
        </met:checkRetrieveStatus>
    </soapenv:Body>
</soapenv:Envelope>"""
    return soap.encode("utf-8")


def _soap_post(url: str, body: bytes, action: str) -> etree._Element:
    """POST a SOAP envelope and return the parsed response root element."""
    resp = requests.post(
        url, data=body,
        headers={"Content-Type": "text/xml; charset=UTF-8", "SOAPAction": action},
        timeout=60
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Metadata API call '{action}' failed "
            f"(HTTP {resp.status_code}): {resp.text[:600]}"
        )
    return etree.fromstring(resp.content)


def _find_el(root: etree._Element, local_name: str) -> Optional[etree._Element]:
    return root.find(f".//{{{METADATA_NS}}}{local_name}")


def _fetch_all_layouts(instance_url: str, token: str, api_version: str,
                       layout_names: List[str]) -> Dict[str, str]:
    """
    Retrieve all requested layout XMLs from one org in a single Metadata API call.
    Returns {layout_base_name: xml_string}.  Layouts not found in the org are absent.
    """
    meta_url = f"{instance_url}/services/Soap/m/{api_version}"

    # 1. Start retrieve
    body = _build_retrieve_envelope(token, api_version, layout_names)
    root = _soap_post(meta_url, body, "retrieve")
    id_el = _find_el(root, "id")
    if id_el is None:
        raise RuntimeError(
            f"No retrieve ID returned from {instance_url}. "
            "Check org credentials and API version."
        )
    retrieve_id = id_el.text

    # 2. Poll until done (max 120 s)
    deadline = time.time() + 120
    while time.time() < deadline:
        status_body = _build_status_envelope(token, api_version, retrieve_id)
        status_root = _soap_post(meta_url, status_body, "checkRetrieveStatus")

        done_el = _find_el(status_root, "done")
        if done_el is None or done_el.text != "true":
            time.sleep(3)
            continue

        # Check for hard failure
        status_el = _find_el(status_root, "status")
        if status_el is not None and status_el.text == "Failed":
            err_el = _find_el(status_root, "errorMessage")
            raise RuntimeError(
                f"Retrieve failed on {instance_url}: "
                f"{err_el.text if err_el is not None else 'unknown error'}"
            )

        # 3. Extract ZIP
        zip_el = _find_el(status_root, "zipFile")
        if zip_el is None or not zip_el.text:
            logger.warning("Retrieve completed but ZIP is empty — no layouts found.")
            return {}

        zip_bytes = base64.b64decode(zip_el.text)
        return _extract_layouts_from_zip(zip_bytes)

    raise TimeoutError(
        f"Metadata API retrieve from {instance_url} did not complete within 120 s."
    )


def _extract_layouts_from_zip(zip_bytes: bytes) -> Dict[str, str]:
    """
    Unpack the retrieve ZIP and return {layout_base_name: xml_string}.

    Salesforce stores layouts at:
        unpackaged/layouts/Object-Layout Name.layout-meta.xml
    The key returned is the base name with suffixes stripped, e.g.:
        "Account-Account Layout"
    """
    result: Dict[str, str] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for entry in zf.namelist():
            lower = entry.lower()
            if "/layouts/" not in lower:
                continue
            if not (lower.endswith(".layout-meta.xml") or lower.endswith(".layout")):
                continue

            base = entry.split("/")[-1]
            for suffix in (".layout-meta.xml", ".layout"):
                if base.lower().endswith(suffix):
                    base = base[: -len(suffix)]
                    break

            result[base] = zf.read(entry).decode("utf-8")

    return result


# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT XML PARSER
# ─────────────────────────────────────────────────────────────────────────────

def _parse_layout(xml_content: str) -> Dict[str, Any]:
    """
    Parse a Salesforce Layout XML and return a structured dict:
        {
            "sections":       {section_label: [field_api_name, ...]},
            "all_fields":     set of every field API name in the layout,
            "related_lists":  set of relatedList API names,
        }

    Handles blank spacer items (layoutItems with no <field> child) gracefully.
    """
    ns = {"m": METADATA_NS}
    try:
        root = etree.fromstring(xml_content.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        raise ValueError(f"Could not parse layout XML: {exc}") from exc

    sections: Dict[str, List[str]] = {}
    all_fields: Set[str] = set()
    related_lists: Set[str] = set()

    # ── layoutSections ──────────────────────────────────────────────────────
    for section in root.findall("m:layoutSections", ns):
        lbl_el = section.find("m:label", ns)
        label = (lbl_el.text or "").strip() if lbl_el is not None else "Unnamed Section"

        section_fields: List[str] = []
        for col in section.findall("m:layoutColumns", ns):
            for item in col.findall("m:layoutItems", ns):
                f_el = item.find("m:field", ns)
                if f_el is not None and f_el.text and f_el.text.strip():
                    fname = f_el.text.strip()
                    section_fields.append(fname)
                    all_fields.add(fname)

        sections[label] = section_fields

    # ── relatedLists ─────────────────────────────────────────────────────────
    for rl in root.findall("m:relatedLists", ns):
        rl_el = rl.find("m:relatedList", ns)
        if rl_el is not None and rl_el.text and rl_el.text.strip():
            related_lists.add(rl_el.text.strip())

    return {
        "sections": sections,
        "all_fields": all_fields,
        "related_lists": related_lists,
    }


# ─────────────────────────────────────────────────────────────────────────────
# COMPARISON ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def _compare(source: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
    """Diff two parsed layout dicts. All sets are treated as unordered."""
    src_fields: Set[str] = source["all_fields"]
    tgt_fields: Set[str] = target["all_fields"]
    src_sections: Set[str] = set(source["sections"].keys())
    tgt_sections: Set[str] = set(target["sections"].keys())
    src_rl: Set[str] = source["related_lists"]
    tgt_rl: Set[str] = target["related_lists"]

    return {
        "fields_missing_in_target":        sorted(src_fields - tgt_fields),
        "fields_extra_in_target":          sorted(tgt_fields - src_fields),
        "sections_missing_in_target":      sorted(src_sections - tgt_sections),
        "sections_extra_in_target":        sorted(tgt_sections - src_sections),
        "related_lists_missing_in_target": sorted(src_rl - tgt_rl),
        "related_lists_extra_in_target":   sorted(tgt_rl - src_rl),
        "source_field_count":              len(src_fields),
        "target_field_count":              len(tgt_fields),
        "source_section_count":            len(src_sections),
        "target_section_count":            len(tgt_sections),
        "source_related_list_count":       len(src_rl),
        "target_related_list_count":       len(tgt_rl),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CSV HELPERS
# ─────────────────────────────────────────────────────────────────────────────

CSV_COLUMNS = [
    "Source Layout Name",
    "Target Layout Name",
    "Status",
    "Fields Missing in Target",
    "Fields Extra in Target",
    "Fields Missing Count",
    "Fields Extra Count",
    "Sections Missing in Target",
    "Sections Extra in Target",
    "Sections Missing Count",
    "Sections Extra Count",
    "Related Lists Missing in Target",
    "Related Lists Extra in Target",
    "Related Lists Missing Count",
    "Related Lists Extra Count",
    "Source Field Count",
    "Target Field Count",
    "Source Section Count",
    "Target Section Count",
    "Source Related List Count",
    "Target Related List Count",
]


def _cell(lst: List[str]) -> str:
    """Semicolon-separated cell value for multi-value fields."""
    return "; ".join(lst) if lst else ""


def _write_csv(rows: List[Dict[str, Any]], filepath: str) -> None:
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _blank_row(source_name: str, target_name: str, status: str) -> Dict[str, Any]:
    row = {col: "" for col in CSV_COLUMNS}
    row["Source Layout Name"] = source_name
    row["Target Layout Name"] = target_name
    row["Status"] = status
    return row


# ─────────────────────────────────────────────────────────────────────────────
# MCP TOOL
# ─────────────────────────────────────────────────────────────────────────────

@register_tool
def compare_page_layouts(
    layout_names: str,
    source_org_user_id: str = None,
    target_org_user_id: str = None,
    output_filename: str = None,
) -> str:
    """
    Compare Salesforce page layouts between two orgs and produce a CSV diff report.

    Retrieves the full layout XML from source and target orgs via the Metadata API
    (one batched API call per org), then compares sections, fields, and related lists —
    one CSV row per layout.

    Args:
        layout_names:
            Comma-separated layout API names in "Object-Layout Name" format.
            Example: "Account-Account Layout,Contact-Contact Layout,Case-Case Layout"
            Tip: find exact names in Setup > Object Manager > [Object] > Page Layouts.

        source_org_user_id:
            user_id of the SOURCE org (from list_connected_orgs output).
            Leave blank to use the currently active / most recently logged-in org.

        target_org_user_id:
            user_id of the TARGET org (from list_connected_orgs output).
            Leave blank to use the currently active org.
            If both are blank (or identical), the layout is compared against itself
            — all diffs will be zero, useful for verifying layout structure.

        output_filename:
            Optional CSV filename saved to ~/Documents/.
            Defaults to page_layout_comparison_<timestamp>.csv.

    CSV columns produced:
        Source Layout Name        — layout name fetched from the source org
        Target Layout Name        — layout name fetched from the target org
        Status                    — Compared | Source Not Found | Target Not Found |
                                    Not Found in Either Org | Parse Error
        Fields Missing in Target  — semicolon-separated field API names
        Fields Extra in Target    — semicolon-separated field API names
        Fields Missing Count      — integer
        Fields Extra Count        — integer
        Sections Missing in Target — semicolon-separated section labels
        Sections Extra in Target   — semicolon-separated section labels
        Sections Missing Count    — integer
        Sections Extra Count      — integer
        Related Lists Missing in Target — semicolon-separated relatedList names
        Related Lists Extra in Target   — semicolon-separated relatedList names
        Related Lists Missing Count — integer
        Related Lists Extra Count   — integer
        Source Field Count        — total fields on source layout
        Target Field Count        — total fields on target layout
        Source Section Count      — total sections on source layout
        Target Section Count      — total sections on target layout
        Source Related List Count — total related lists on source layout
        Target Related List Count — total related lists on target layout

    Example:
        # Compare one layout between two connected orgs
        compare_page_layouts(
            layout_names="Account-Account Layout",
            source_org_user_id="0051a000001XyzABC",
            target_org_user_id="0051b000001DefGHI"
        )

        # Compare multiple layouts, custom filename
        compare_page_layouts(
            layout_names="Account-Account Layout,Contact-Contact Layout,Case-Case Layout",
            source_org_user_id="0051a000001XyzABC",
            target_org_user_id="0051b000001DefGHI",
            output_filename="layout_audit_q1_2026.csv"
        )

    Notes:
        - Layout names are case-sensitive and must match the Salesforce API name exactly.
        - Run list_connected_orgs first to get the user_id values.
        - The CSV is saved with UTF-8 BOM encoding so it opens cleanly in Excel.
        - Fields, sections, and related lists are compared by their API names /
          labels, not by position in the layout.

    Created by Sameer
    """
    try:
        # ── 1. Parse and validate layout names ──────────────────────────────
        names = [n.strip() for n in layout_names.split(",") if n.strip()]
        if not names:
            return format_error_response(
                ValueError("layout_names must not be empty."),
                context="compare_page_layouts"
            )

        # ── 2. Get org credentials ───────────────────────────────────────────
        try:
            src_url, src_token, api_ver = _get_org_credentials(source_org_user_id)
        except Exception as e:
            return format_error_response(e, context="compare_page_layouts (source org)")

        try:
            tgt_url, tgt_token, _ = _get_org_credentials(target_org_user_id)
        except Exception as e:
            return format_error_response(e, context="compare_page_layouts (target org)")

        same_org = (src_url == tgt_url and src_token == tgt_token)

        # ── 3. Fetch layouts — one batched retrieve per org ──────────────────
        try:
            src_layouts = _fetch_all_layouts(src_url, src_token, api_ver, names)
        except Exception as e:
            return format_error_response(e, context="compare_page_layouts (fetch source layouts)")

        if same_org:
            tgt_layouts = src_layouts  # no duplicate API call
        else:
            try:
                tgt_layouts = _fetch_all_layouts(tgt_url, tgt_token, api_ver, names)
            except Exception as e:
                return format_error_response(e, context="compare_page_layouts (fetch target layouts)")

        # ── 4. Compare each layout ───────────────────────────────────────────
        csv_rows: List[Dict[str, Any]] = []
        summary: List[Dict[str, Any]] = []

        for name in names:
            src_xml = src_layouts.get(name)
            tgt_xml = tgt_layouts.get(name)

            # Handle not-found cases
            if src_xml is None and tgt_xml is None:
                csv_rows.append(_blank_row(name, name, "Not Found in Either Org"))
                summary.append({"layout": name, "status": "not_found_both"})
                continue

            if src_xml is None:
                csv_rows.append(_blank_row(name, name, "Source Not Found"))
                summary.append({"layout": name, "status": "source_not_found"})
                continue

            if tgt_xml is None:
                csv_rows.append(_blank_row(name, name, "Target Not Found"))
                summary.append({"layout": name, "status": "target_not_found"})
                continue

            # Parse both XMLs
            try:
                src_data = _parse_layout(src_xml)
                tgt_data = _parse_layout(tgt_xml)
            except Exception as parse_err:
                csv_rows.append(_blank_row(name, name, f"Parse Error: {parse_err}"))
                summary.append({"layout": name, "status": "parse_error", "error": str(parse_err)})
                continue

            diff = _compare(src_data, tgt_data)

            row = _blank_row(name, name, "Compared")
            row["Fields Missing in Target"]        = _cell(diff["fields_missing_in_target"])
            row["Fields Extra in Target"]           = _cell(diff["fields_extra_in_target"])
            row["Fields Missing Count"]             = len(diff["fields_missing_in_target"])
            row["Fields Extra Count"]               = len(diff["fields_extra_in_target"])
            row["Sections Missing in Target"]       = _cell(diff["sections_missing_in_target"])
            row["Sections Extra in Target"]         = _cell(diff["sections_extra_in_target"])
            row["Sections Missing Count"]           = len(diff["sections_missing_in_target"])
            row["Sections Extra Count"]             = len(diff["sections_extra_in_target"])
            row["Related Lists Missing in Target"]  = _cell(diff["related_lists_missing_in_target"])
            row["Related Lists Extra in Target"]    = _cell(diff["related_lists_extra_in_target"])
            row["Related Lists Missing Count"]      = len(diff["related_lists_missing_in_target"])
            row["Related Lists Extra Count"]        = len(diff["related_lists_extra_in_target"])
            row["Source Field Count"]               = diff["source_field_count"]
            row["Target Field Count"]               = diff["target_field_count"]
            row["Source Section Count"]             = diff["source_section_count"]
            row["Target Section Count"]             = diff["target_section_count"]
            row["Source Related List Count"]        = diff["source_related_list_count"]
            row["Target Related List Count"]        = diff["target_related_list_count"]

            csv_rows.append(row)
            summary.append({
                "layout":                 name,
                "status":                 "compared",
                "fields_missing":         len(diff["fields_missing_in_target"]),
                "fields_extra":           len(diff["fields_extra_in_target"]),
                "sections_missing":       len(diff["sections_missing_in_target"]),
                "sections_extra":         len(diff["sections_extra_in_target"]),
                "related_lists_missing":  len(diff["related_lists_missing_in_target"]),
                "related_lists_extra":    len(diff["related_lists_extra_in_target"]),
            })

        # ── 5. Write CSV ──────────────────────────────────────────────────────
        # Save to Documents/ folder in the project root (same as other export tools)
        docs_dir = os.path.join(os.getcwd(), "Documents")
        os.makedirs(docs_dir, exist_ok=True)

        if not output_filename:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f"page_layout_comparison_{timestamp}.csv"
        elif not output_filename.lower().endswith(".csv"):
            output_filename += ".csv"

        # If caller passed a full path, use it as-is; otherwise put in Documents/
        if os.path.dirname(output_filename):
            csv_path = os.path.abspath(output_filename)
        else:
            csv_path = os.path.join(docs_dir, output_filename)
        _write_csv(csv_rows, csv_path)

        compared   = [s for s in summary if s["status"] == "compared"]
        not_found  = [s for s in summary if "not_found" in s.get("status", "")]
        errors     = [s for s in summary if s.get("status") == "parse_error"]

        return format_success_response({
            "message":          f"Compared {len(names)} layout(s). CSV report saved.",
            "csv_file":         csv_path,
            "total_layouts":    len(names),
            "compared":         len(compared),
            "not_found":        len(not_found),
            "errors":           len(errors),
            "same_org":         same_org,
            "source_org":       src_url,
            "target_org":       tgt_url,
            "api_version":      api_ver,
            "summary":          summary,
        })

    except Exception as e:
        logger.exception("compare_page_layouts failed")
        return format_error_response(e, context="compare_page_layouts")

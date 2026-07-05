from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict


ReportState = Literal["MATCH", "WARN", "SUSPICIOUS"]
InputSourceKind = Literal["input_json", "mapper", "manual", "unknown"]
VisualizationProducer = Literal["comparator", "report_assembler", "renderer_lazy"]


class InputSourceDescriptor(TypedDict, total=False):
    kind: InputSourceKind
    mapper: Optional[str]
    original_file_name: Optional[str]
    original_sha256: Optional[str]


class ReportInputDescriptor(TypedDict, total=False):
    label: str
    file_name: Optional[str]
    path: Optional[str]
    sha256: Optional[str]
    source: InputSourceDescriptor


class ReportFormatDescriptor(TypedDict, total=False):
    name: str
    version: str


class SectionStatistics(TypedDict):
    compared: int
    changed: int
    matched: int
    only_reference: int
    only_profile: int


class RequestedVisualization(TypedDict, total=False):
    type: str
    variant: Optional[str]


class AvailableVisualization(TypedDict, total=False):
    type: str
    variant: Optional[str]
    producer: VisualizationProducer
    source: str
    rows: List[Dict[str, Any]]
    cells: List[Dict[str, Any]]


class UnavailableVisualization(TypedDict, total=False):
    type: str
    variant: Optional[str]
    reason: str


class SectionVisualizationPayload(TypedDict, total=False):
    requested: List[RequestedVisualization]
    available: Dict[str, AvailableVisualization]
    unavailable: List[UnavailableVisualization]


class SectionOriginalRows(TypedDict, total=False):
    rows: List[Dict[str, Any]]


class SectionOriginalPayload(TypedDict, total=False):
    reference: SectionOriginalRows
    profile: SectionOriginalRows


class SectionResultsPayload(TypedDict, total=False):
    state: ReportState
    stats: SectionStatistics
    labels: Dict[str, str]
    matches: List[Dict[str, Any]]
    differences: Dict[str, List[Dict[str, Any]]]
    raw_differences: List[Dict[str, Any]]


class SectionMetaPayload(TypedDict, total=False):
    name: str
    comparator: Optional[str]
    match_key: Optional[str]
    show_key: Optional[str]
    report: Dict[str, Any]
    severity: Dict[str, Any]


class ReportSectionPayload(TypedDict, total=False):
    meta: SectionMetaPayload
    original: SectionOriginalPayload
    results: SectionResultsPayload
    visualizations: SectionVisualizationPayload
    artifacts: Dict[str, Any]


class ReportSummaryPayload(TypedDict, total=False):
    overall: ReportState
    state_counts: Dict[str, int]
    result_counts: SectionStatistics
    by_section: Dict[str, Dict[str, int]]


class ReportDocumentV2(TypedDict, total=False):
    format: ReportFormatDescriptor
    meta: Dict[str, Any]
    inputs: Dict[str, ReportInputDescriptor]
    summary: ReportSummaryPayload
    sections: Dict[str, ReportSectionPayload]

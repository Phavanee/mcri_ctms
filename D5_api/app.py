import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from pymongo import MongoClient

MONGO_URI = os.environ.get(
    "MONGO_URI",
    "mongodb://root:root@ac-4io06mf-shard-00-00.8pmfqqn.mongodb.net:27017,"
    "ac-4io06mf-shard-00-01.8pmfqqn.mongodb.net:27017,"
    "ac-4io06mf-shard-00-02.8pmfqqn.mongodb.net:27017/"
    "?ssl=true&replicaSet=atlas-d35um1-shard-0&authSource=admin&appName=Cluster0",
)
DB_NAME = os.environ.get("DB_NAME", "mcri")
AE_COLLECTION = os.environ.get("AE_COLLECTION_NAME", "adverse_events")
INTERVENTIONS_COLLECTION = os.environ.get("INTERVENTIONS_COLLECTION_NAME", "interventions")
PATIENTS_COLLECTION = os.environ.get("PATIENTS_COLLECTION_NAME", "patients")
CT_COLLECTION = os.environ.get("CT_COLLECTION_NAME", "clinical_trials")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]


def _count_patients(field: str, value: str) -> dict[str, Any]:
    return {
        "$size": {
            "$filter": {
                "input": "$enrolled_patients",
                "as": "p",
                "cond": {"$eq": [f"$$p.{field}", value]},
            }
        }
    }


def _age_expr_conditions(age_min: Optional[int], age_max: Optional[int]) -> list[dict[str, Any]]:
    age_years = {
        "$dateDiff": {
            "startDate": {"$dateFromString": {"dateString": "$date_of_birth"}},
            "endDate": "$$NOW",
            "unit": "year",
        }
    }
    conditions = []
    if age_min is not None:
        conditions.append({"$gte": [age_years, age_min]})
    if age_max is not None:
        conditions.append({"$lte": [age_years, age_max]})
    return conditions


app = FastAPI(
    title="MCRI Clinical Trials API",
    description="FastAPI endpoints for analytical requirements ar1–ar10.",
)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "MCRI Clinical Trials API", "docs": "/docs"}


@app.get("/ar1/trials")
def ar1_filter_trials(
    trial_status: Optional[str] = Query(None, alias="status"),
    trial_phase: Optional[str] = Query(None, alias="phase"),
    trial_sponsor: Optional[str] = Query(None, alias="sponsor"),
    condition: Optional[str] = None,
    site: Optional[str] = None,
    enrolment_target_min: Optional[int] = None,
    enrolment_target_max: Optional[int] = None,
    start_date_from: Optional[str] = None,
    start_date_to: Optional[str] = None,
    estimated_end_date_from: Optional[str] = None,
    estimated_end_date_to: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Filter clinical trials by status, phase, sponsor, and other attributes."""
    query: dict[str, Any] = {}
    if trial_status:
        query["status"] = trial_status
    if trial_phase:
        query["phase"] = trial_phase
    if trial_sponsor:
        query["sponsor"] = trial_sponsor
    if condition:
        query["conditions"] = condition
    if site:
        query["sites"] = site

    enrolment_filter: dict[str, Any] = {}
    if enrolment_target_min is not None:
        enrolment_filter["$gte"] = enrolment_target_min
    if enrolment_target_max is not None:
        enrolment_filter["$lte"] = enrolment_target_max
    if enrolment_filter:
        query["enrolment_target"] = enrolment_filter

    start_date_filter: dict[str, Any] = {}
    if start_date_from:
        start_date_filter["$gte"] = start_date_from
    if start_date_to:
        start_date_filter["$lte"] = start_date_to
    if start_date_filter:
        query["start_date"] = start_date_filter

    end_date_filter: dict[str, Any] = {}
    if estimated_end_date_from:
        end_date_filter["$gte"] = estimated_end_date_from
    if estimated_end_date_to:
        end_date_filter["$lte"] = estimated_end_date_to
    if end_date_filter:
        query["estimated_end_date"] = end_date_filter

    projection = {
        "_id": 0,
        "trial_id": 1,
        "title": 1,
        "short_title": 1,
        "phase": 1,
        "status": 1,
        "sponsor": 1,
        "conditions": 1,
        "sites": 1,
        "enrolment_target": 1,
        "enrolled_count": 1,
        "start_date": 1,
        "estimated_end_date": 1,
    }
    return list(db[CT_COLLECTION].find(query, projection))


@app.get("/ar2/trials/{trial_id}/patients")
def ar2_trial_patients(
    trial_id: str,
    patient_gender: Optional[str] = Query(None, alias="gender"),
    patient_ethnicity: Optional[str] = Query(None, alias="ethnicity"),
    patient_site: Optional[str] = Query(None, alias="site_id"),
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    smoking_status: Optional[str] = None,
    diagnosis_icd10: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Retrieve patients enrolled in a trial with optional demographic/clinical filters."""
    query: dict[str, Any] = {"enrolled_trials": trial_id}
    if patient_gender:
        query["gender"] = patient_gender
    if patient_ethnicity:
        query["ethnicity"] = patient_ethnicity
    if patient_site:
        query["site_id"] = patient_site
    if smoking_status:
        query["smoking_status"] = smoking_status
    if diagnosis_icd10:
        query["diagnosis.icd10_code"] = diagnosis_icd10

    expr_conditions = _age_expr_conditions(age_min, age_max)
    if expr_conditions:
        query["$expr"] = (
            {"$and": expr_conditions} if len(expr_conditions) > 1 else expr_conditions[0]
        )

    projection = {
        "_id": 0,
        "patient_id": 1,
        "name": 1,
        "date_of_birth": 1,
        "gender": 1,
        "ethnicity": 1,
        "blood_type": 1,
        "bmi": 1,
        "smoking_status": 1,
        "diagnosis": 1,
        "comorbidities": 1,
        "site_id": 1,
    }
    return list(db[PATIENTS_COLLECTION].find(query, projection))


@app.get("/ar3/patients")
def ar3_search_patients(
    gender: Optional[str] = None,
    ethnicity: Optional[str] = None,
    site_id: Optional[str] = None,
    icd10_code: Optional[str] = None,
    smoking_status: Optional[str] = None,
    comorbidity_search: Optional[str] = None,
    min_comorbidity_count: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Search patients by demographic or clinical criteria."""
    query: dict[str, Any] = {}
    if gender:
        query["gender"] = gender
    if ethnicity:
        query["ethnicity"] = ethnicity
    if site_id:
        query["site_id"] = site_id
    if icd10_code:
        query["diagnosis.icd10_code"] = icd10_code
    if smoking_status:
        query["smoking_status"] = smoking_status
    if comorbidity_search:
        query["comorbidities"] = {
            "$elemMatch": {"$regex": comorbidity_search, "$options": "i"}
        }
    if min_comorbidity_count is not None:
        query["$expr"] = {"$gte": [{"$size": "$comorbidities"}, min_comorbidity_count]}

    return list(db[PATIENTS_COLLECTION].find(query, {"_id": 0}))


@app.get("/ar4/patients/{patient_id}/adverse-events")
def ar4_patient_adverse_events(
    patient_id: str,
    min_grade: Optional[int] = None,
    serious_only: bool = False,
) -> list[dict[str, Any]]:
    """Retrieve adverse events for a patient with optional severity filters."""
    query: dict[str, Any] = {"patient_id": patient_id}
    if min_grade is not None:
        query["ctcae_grade"] = {"$gte": min_grade}
    if serious_only:
        query["serious"] = True

    return list(db[AE_COLLECTION].find(query, {"_id": 0}))


@app.get("/ar5/adverse-events/by-intervention-type")
def ar5_ae_summary_by_intervention_type() -> list[dict[str, Any]]:
    """Aggregate adverse events grouped by intervention type."""
    pipeline = [
        {
            "$lookup": {
                "from": INTERVENTIONS_COLLECTION,
                "localField": "intervention_id",
                "foreignField": "intervention_id",
                "as": "intervention",
            }
        },
        {"$unwind": "$intervention"},
        {
            "$group": {
                "_id": "$intervention.type",
                "total_events": {"$sum": 1},
                "serious_events": {"$sum": {"$cond": ["$serious", 1, 0]}},
            }
        },
        {
            "$project": {
                "_id": 0,
                "intervention_type": "$_id",
                "total_events": 1,
                "serious_events": 1,
                "serious_proportion": {
                    "$round": [{"$divide": ["$serious_events", "$total_events"]}, 4]
                },
            }
        },
        {"$sort": {"intervention_type": 1}},
    ]
    return list(db[AE_COLLECTION].aggregate(pipeline))


@app.get("/ar6/trials/enrolment-progress")
def ar6_enrolment_progress(
    sponsor: Optional[str] = None,
    phase: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Calculate enrolment completion per trial with demographic breakdowns."""
    match_stage: dict[str, Any] = {}
    if sponsor:
        match_stage["sponsor"] = sponsor
    if phase:
        match_stage["phase"] = phase

    pipeline: list[dict[str, Any]] = []
    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend([
        {
            "$lookup": {
                "from": PATIENTS_COLLECTION,
                "localField": "trial_id",
                "foreignField": "enrolled_trials",
                "as": "enrolled_patients",
            }
        },
        {
            "$facet": {
                "trial": [
                    {
                        "$project": {
                            "_id": 0,
                            "trial_id": 1,
                            "title": 1,
                            "sponsor": 1,
                            "phase": 1,
                            "status": 1,
                            "enrolment_target": 1,
                            "enrolled_count": 1,
                            "patients_remaining": {
                                "$subtract": ["$enrolment_target", "$enrolled_count"]
                            },
                            "enrolment_completion_pct": {
                                "$round": [
                                    {
                                        "$multiply": [
                                            {
                                                "$divide": [
                                                    "$enrolled_count",
                                                    "$enrolment_target",
                                                ]
                                            },
                                            100,
                                        ]
                                    },
                                    2,
                                ]
                            },
                            "gender_breakdown": {
                                "Male": _count_patients("gender", "Male"),
                                "Female": _count_patients("gender", "Female"),
                                "Non-binary": _count_patients("gender", "Non-binary"),
                                "Prefer not to say": _count_patients(
                                    "gender", "Prefer not to say"
                                ),
                            },
                            "ethnicity_breakdown": {
                                "Malay": _count_patients("ethnicity", "Malay"),
                                "Chinese": _count_patients("ethnicity", "Chinese"),
                                "Indian": _count_patients("ethnicity", "Indian"),
                                "Caucasian": _count_patients("ethnicity", "Caucasian"),
                                "African": _count_patients("ethnicity", "African"),
                                "Hispanic": _count_patients("ethnicity", "Hispanic"),
                                "Other": _count_patients("ethnicity", "Other"),
                            },
                            "smoking_breakdown": {
                                "Never": _count_patients("smoking_status", "Never"),
                                "Former": _count_patients("smoking_status", "Former"),
                                "Current": _count_patients("smoking_status", "Current"),
                            },
                        }
                    }
                ],
                "sites": [
                    {"$unwind": "$enrolled_patients"},
                    {
                        "$group": {
                            "_id": "$enrolled_patients.site_id",
                            "count": {"$sum": 1},
                        }
                    },
                    {
                        "$group": {
                            "_id": None,
                            "site_breakdown": {
                                "$push": {"k": "$_id", "v": "$count"}
                            },
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "site_breakdown": {"$arrayToObject": "$site_breakdown"},
                        }
                    },
                ],
            }
        },
        {
            "$project": {
                "trial": {"$arrayElemAt": ["$trial", 0]},
                "site_breakdown": {
                    "$ifNull": [
                        {"$arrayElemAt": ["$sites.site_breakdown", 0]},
                        {},
                    ]
                },
            }
        },
        {
            "$replaceRoot": {
                "newRoot": {
                    "$mergeObjects": ["$trial", {"site_breakdown": "$site_breakdown"}]
                }
            }
        },
        {"$sort": {"enrolment_completion_pct": -1}},
    ])
    return list(db[CT_COLLECTION].aggregate(pipeline))


@app.get("/ar7/trials/{trial_id}/adverse-events/causality-severity-matrix")
def ar7_ae_causality_severity_matrix(trial_id: str) -> list[dict[str, Any]]:
    """Cross-tabulation of adverse events by causality rating and CTCAE grade."""
    pipeline = [
        {"$match": {"trial_id": trial_id}},
        {
            "$group": {
                "_id": {"causality": "$causality", "ctcae_grade": "$ctcae_grade"},
                "count": {"$sum": 1},
            }
        },
        {
            "$project": {
                "_id": 0,
                "causality": "$_id.causality",
                "ctcae_grade": "$_id.ctcae_grade",
                "count": 1,
            }
        },
        {"$sort": {"causality": 1, "ctcae_grade": 1}},
    ]
    return list(db[AE_COLLECTION].aggregate(pipeline))


@app.get("/ar8/patients/comorbidity-ae-burden")
def ar8_comorbidity_ae_burden(
    comorbidity_threshold: int = Query(
        2, description="Patients with more than this many comorbidities"
    ),
) -> list[dict[str, Any]]:
    """Patients above a comorbidity threshold with total and serious AE counts."""
    pipeline = [
        {"$addFields": {"comorbidity_count": {"$size": "$comorbidities"}}},
        {"$match": {"comorbidity_count": {"$gt": comorbidity_threshold}}},
        {
            "$lookup": {
                "from": AE_COLLECTION,
                "localField": "patient_id",
                "foreignField": "patient_id",
                "as": "adverse_events",
            }
        },
        {
            "$project": {
                "_id": 0,
                "patient_id": 1,
                "name": 1,
                "comorbidity_count": 1,
                "total_ae_count": {"$size": "$adverse_events"},
                "serious_ae_count": {
                    "$size": {
                        "$filter": {
                            "input": "$adverse_events",
                            "as": "ae",
                            "cond": {"$eq": ["$$ae.serious", True]},
                        }
                    }
                },
            }
        },
        {"$sort": {"comorbidity_count": -1, "total_ae_count": -1}},
    ]
    return list(db[PATIENTS_COLLECTION].aggregate(pipeline))


@app.get("/ar9/interventions/by-target")
def ar9_interventions_by_target(
    gene_symbol: Optional[str] = None,
    protein_target: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Interventions targeting a gene symbol or protein with trial context."""
    target_filters: list[dict[str, Any]] = []
    if gene_symbol:
        target_filters.append({"target_gene": gene_symbol})
    if protein_target:
        target_filters.append({"target_protein": protein_target})

    if not target_filters:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of gene_symbol or protein_target",
        )

    match_stage = (
        {"$or": target_filters} if len(target_filters) > 1 else target_filters[0]
    )

    pipeline = [
        {"$match": match_stage},
        {
            "$lookup": {
                "from": CT_COLLECTION,
                "localField": "trial_id",
                "foreignField": "trial_id",
                "as": "trial",
            }
        },
        {"$unwind": "$trial"},
        {
            "$project": {
                "_id": 0,
                "intervention_id": 1,
                "name": 1,
                "type": 1,
                "target_gene": 1,
                "target_protein": 1,
                "regulatory_status": 1,
                "trial_id": 1,
                "trial_title": "$trial.title",
                "trial_phase": "$trial.phase",
                "trial_status": "$trial.status",
                "trial_sponsor": "$trial.sponsor",
            }
        },
    ]
    return list(db[INTERVENTIONS_COLLECTION].aggregate(pipeline))


@app.get("/ar10/adverse-events/monthly-trend")
def ar10_monthly_ae_trend(
    trial_id: Optional[str] = None,
    intervention_type: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Monthly adverse event counts grouped by year and month."""
    pipeline: list[dict[str, Any]] = []

    match_stage: dict[str, Any] = {}
    if trial_id:
        match_stage["trial_id"] = trial_id
    if match_stage:
        pipeline.append({"$match": match_stage})

    if intervention_type:
        pipeline.extend([
            {
                "$lookup": {
                    "from": INTERVENTIONS_COLLECTION,
                    "localField": "intervention_id",
                    "foreignField": "intervention_id",
                    "as": "intervention",
                }
            },
            {"$unwind": "$intervention"},
            {"$match": {"intervention.type": intervention_type}},
        ])

    pipeline.extend([
        {
            "$addFields": {
                "onset_year": {
                    "$year": {"$dateFromString": {"dateString": "$onset_date"}}
                },
                "onset_month": {
                    "$month": {"$dateFromString": {"dateString": "$onset_date"}}
                },
            }
        },
        {
            "$group": {
                "_id": {"year": "$onset_year", "month": "$onset_month"},
                "ae_count": {"$sum": 1},
            }
        },
        {
            "$project": {
                "_id": 0,
                "year": "$_id.year",
                "month": "$_id.month",
                "ae_count": 1,
            }
        },
        {"$sort": {"year": 1, "month": 1}},
    ])
    return list(db[AE_COLLECTION].aggregate(pipeline))

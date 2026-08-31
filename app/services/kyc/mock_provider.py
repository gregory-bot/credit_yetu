"""Sandbox provider — deterministic, clearly-labelled fake data.

IMPORTANT: this returns synthetic data only. Every response carries
``"sandbox": true`` and ``"provider": "mock"`` so it can never be mistaken for a
real verification. It exists so the whole system runs end-to-end in development
without touching gated data sources. Do not remove the sandbox markers.
"""
from __future__ import annotations

import hashlib
import random

from app.services.kyc.base import IdentityProvider


def _seeded(identifier: str) -> random.Random:
    seed = int(hashlib.sha256(identifier.encode()).hexdigest(), 16) % (2**32)
    return random.Random(seed)


def _envelope(data: dict, message: str = "OK") -> dict:
    return {"provider": "mock", "sandbox": True, "code": "200.001", "message": message, "data": data}


_FIRST = ["John", "Jane", "Peter", "Mary", "Ann", "David", "Grace", "Paul"]
_SUR = ["Doe", "Kamau", "Otieno", "Wanjiru", "Mwangi", "Achieng", "Njoroge"]


class MockProvider(IdentityProvider):
    name = "mock"

    def _person(self, identifier: str) -> dict:
        r = _seeded(identifier)
        first, sur = r.choice(_FIRST), r.choice(_SUR)
        return {
            "id_number": identifier,
            "first_name": first,
            "surname": sur,
            "other_name": r.choice(_FIRST),
            "full_name": f"{sur} {first}",
            "gender": r.choice(["M", "F"]),
            "date_of_birth": f"{r.randint(1970, 2003)}-{r.randint(1,12):02d}-{r.randint(1,28):02d}",
            "citizenship": "Kenyan",
            "serial_number": str(r.randint(10_000_000, 99_999_999)),
            "place_of_birth": r.choice(["Nairobi", "Kiambu", "Nakuru", "Kisumu", "Eldoret"]),
        }

    def verify_identity(self, identifier: str, **ctx) -> dict:
        return _envelope(self._person(identifier), "Identity verified")

    def verify_passport(self, identifier: str, **ctx) -> dict:
        p = self._person(identifier)
        p.update({"passport_number": identifier, "valid": True, "date_of_expiry": "2034-06-06"})
        return _envelope(p, "Passport details fetched")

    def face_match(self, id_number: str, selfie: bytes, national_id_img: bytes, **ctx) -> dict:
        r = _seeded(id_number + str(len(selfie)))
        score = round(r.uniform(60, 99), 1)
        return _envelope({"match_score": score, "is_match": score >= 75}, "Face match completed")

    def verify_kra_pin(self, identifier: str, search_type: str = "pin", **ctx) -> dict:
        r = _seeded(identifier)
        pin = "A" + str(r.randint(100_000_000, 999_999_999)) + "Z"
        return _envelope(
            {"KRAPIN": pin, "TypeOfTaxpayer": "Individual", "StatusOfPIN": "Active", **self._person(identifier)},
            "Valid PIN",
        )

    def verify_alien_id(self, identifier: str, **ctx) -> dict:
        return _envelope({"alien_id": identifier, "valid": True}, "Alien ID verification successful")

    def crb_metropol(self, identity_number: str, full: bool = False, **ctx) -> dict:
        r = _seeded(identity_number)
        score = r.randint(250, 810)
        data = {
            "identity_number": identity_number,
            "credit_score": score,
            "grade": "AA" if score > 700 else ("B" if score > 550 else "D"),
            "has_fraud": False,
            "no_of_credit_applications": {"last_12_months": r.randint(0, 6)},
            "no_of_enquiries": {"last_12_months": r.randint(0, 10)},
        }
        if full:
            data["account_info"] = [
                {"account_status": r.choice(["Open", "Closed"]),
                 "current_balance": round(r.uniform(0, 50000), 2),
                 "days_in_arrears": r.randint(0, 120)}
                for _ in range(r.randint(1, 4))
            ]
        return _envelope(data, "Metropol report fetched")

    def crb_creditinfo(self, identifier: str, score_only: bool = False, **ctx) -> dict:
        r = _seeded(identifier)
        score = r.randint(250, 800)
        data = {"identifier": identifier, "MobileScore": str(score),
                "MobileScoreRiskGrade": "D1" if score < 500 else "B2"}
        if not score_only:
            data["contracts_open"] = r.randint(0, 5)
            data["worst_days_in_arrears"] = r.randint(0, 400)
        return _envelope(data, "Creditinfo report fetched")

    def phone_hakikisha(self, identifier: str, **ctx) -> dict:
        p = self._person(ctx.get("national_id", identifier))
        return _envelope({"name": p["full_name"], "phone_number": identifier,
                          "is_valid": True, "is_active": True}, "Phone number details fetched")

    def mpesa_kyc(self, phone_number: str, identifier: str, **ctx) -> dict:
        r = _seeded(phone_number + identifier)
        match = r.random() > 0.15
        return _envelope({"responseCode": "4000" if match else "4001",
                          "responseMessage": "Details match successfully" if match else "No match",
                          "status": match}, "Mpesa KYC completed")

    def sim_swap(self, identifier: str, **ctx) -> dict:
        return _envelope({"customerNumber": identifier, "lastSwapDate": "", "responseCode": "200"}, "Sim swap checked")

    def phone_search(self, identifier: str, **ctx) -> dict:
        r = _seeded(identifier)
        numbers = ["2547" + str(r.randint(10_000_000, 99_999_999)) for _ in range(r.randint(1, 4))]
        return _envelope({"id_number": identifier, "phone_contacts": numbers}, "Phone search completed")

    def bank_account_validation(self, identifier: str, bank: str, **ctx) -> dict:
        p = self._person(identifier)
        return _envelope({"account_number": identifier, "account_name": p["full_name"].upper(),
                          "bank_name": bank.upper(), "valid": True}, "Bank account validation successful")

    def full_kyc(self, identifier: str, **ctx) -> dict:
        base = self._person(identifier)
        r = _seeded(identifier)
        base.update({
            "employed": r.random() > 0.4,
            "employer_details": {"employerName": r.choice(["ACME LTD", "TECH CO", "SELF"]), "jobGroup": None},
            "KRAPIN": "A" + str(r.randint(100_000_000, 999_999_999)) + "Z",
            "StatusOfPIN": "Active",
        })
        return _envelope(base, "Full KYC fetched")

    def employer_verification(self, identifier: str, **ctx) -> dict:
        r = _seeded(identifier)
        return _envelope({"id_number": identifier, "employed": r.random() > 0.4,
                          "employer_details": {"employerName": r.choice(["ACME LTD", "TECH CO"]), "jobGroup": None}},
                         "Employer verification completed")

    def business_verification(self, registration_no: str, **ctx) -> dict:
        r = _seeded(registration_no)
        return _envelope({
            "registration_number": registration_no,
            "status": "registered",
            "business_name": f"{r.choice(_SUR)} Enterprises Ltd",
            "registration_date": f"{r.randint(2005, 2022)}-{r.randint(1,12):02d}-{r.randint(1,28):02d}",
            "directors": [{"name": f"{r.choice(_FIRST)} {r.choice(_SUR)}", "id_type": "citizen"} for _ in range(r.randint(1, 3))],
            "kra_pin": "P" + str(r.randint(100_000_000, 999_999_999)) + "X",
        }, "Business verification successful")

    def driving_licence(self, identifier: str, **ctx) -> dict:
        p = self._person(identifier)
        p.update({"license_number": "DL-" + identifier, "dl_class": "B", "is_valid": True,
                  "date_of_expiry": "2026-07-19"})
        return _envelope(p, "Driving licence details fetched")

from dataclasses import dataclass, InitVar
import datetime
from enum import Enum
from functools import total_ordering
import re
from typing import Any, Self

from mibig.errors import ValidationError
from mibig.validation import ValidationErrorInfo
from mibig.utils import CDS, INVALID_CHARS, Record


class QualityLevel(Enum):
    QUESTIONABLE = "questionable"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Location:
    begin: int
    end: int

    def __init__(self, begin: int, end: int, validate: bool = True, **kwargs) -> None:
        self.begin = begin
        self.end = end

        if not validate:
            return

        errors = self.validate(**kwargs)
        if errors:
            raise ValidationError(errors)

    @classmethod
    def from_json(cls, raw: dict[str, Any], **kwargs) -> Self:
        begin = raw["from"]
        end = raw["to"]
        if not isinstance(begin, int):
            raise ValueError("Location.from needs to be an integer")
        if not isinstance(end, int):
            raise ValueError("Location.to needs to be an integer")

        return cls(begin, end, **kwargs)

    def to_json(self) -> dict[str, int]:
        return {"from": self.begin, "to": self.end}

    def validate(
        self,
        record: Record | None = None,
        cds: CDS | None = None,
        quality: QualityLevel | None = None,
        **kwargs,
    ) -> list[ValidationErrorInfo]:
        errors: list[ValidationErrorInfo] = []

        if self.begin < 0 and quality != QualityLevel.QUESTIONABLE:
            errors.append(
                ValidationErrorInfo("Location.from", "From coordinate must be positive")
            )
        if self.end < 0 and quality != QualityLevel.QUESTIONABLE:
            errors.append(
                ValidationErrorInfo("Location,to", "To coordinate must be positive")
            )

        if self.begin > self.end:
            errors.append(
                ValidationErrorInfo(
                    "Location",
                    f"Location.from {self.begin} must be less than Location.to {self.end}",
                )
            )

        if record and not quality == QualityLevel.QUESTIONABLE:
            if self.begin > record.seq_len:
                errors.append(
                    ValidationErrorInfo(
                        "Location.from",
                        "Location.from must be less than the sequence length",
                    )
                )
            if self.end > record.seq_len:
                errors.append(
                    ValidationErrorInfo(
                        "Location.to",
                        "Location.to must be less than the sequence length",
                    )
                )

        if cds:
            if self.end > cds.translation_length:
                errors.append(
                    ValidationErrorInfo(
                        "Location.to",
                        "Location.to must be less than the translation length",
                    )
                )
        return errors


class NovelGeneId:
    _inner: str

    def __init__(self, inner: str, validate: bool = True, **kwargs) -> None:
        self._inner = inner

        if not validate:
            return

        errors = self.validate(**kwargs)
        if errors:
            raise ValidationError(errors)

    def __str__(self) -> str:
        return self._inner

    def validate(self, **kwargs) -> list[ValidationErrorInfo]:
        errors: list[ValidationErrorInfo] = []

        if not self._inner:
            errors.append(ValidationErrorInfo("gene_id", "Gene id cannot be empty"))

        if INVALID_CHARS.search(self._inner):
            errors.append(
                ValidationErrorInfo(
                    "gene_id",
                    f"Gene id {self._inner!r} contains invalid characters",
                )
            )

        return errors

    @classmethod
    def from_json(cls, raw: str, **kwargs) -> Self:
        return cls(raw, **kwargs)

    def to_json(self) -> str:
        return self._inner


class GeneId(NovelGeneId):
    def validate(
        self, record: Record | None = None, **kwargs
    ) -> list[ValidationErrorInfo]:
        errors = super().validate()

        if record and not record.get_cds(self._inner):
            errors.append(
                ValidationErrorInfo(
                    "gene_id", f"Gene id {self._inner!r} not found in record"
                )
            )

        return errors


@total_ordering
class Citation:
    VALID_PATTERNS = {
        "pubmed": r"^(\d+)$",
        "doi": r"^10\.\d{4,9}/[-\._;()/:a-zA-Z0-9]+$",
        "patent": r"^(.+)$",
        "url": r"^https?:\/\/(www\\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)$",
    }
    database: str
    value: str

    def __init__(self, database: str, value: str, validate: bool = True) -> None:
        self.database = database
        self.value = value

        if not validate:
            return

        errors = self.validate()
        if errors:
            raise ValidationError(errors)

    def to_json(self) -> str:
        return f"{self.database}:{self.value}"

    @classmethod
    def from_json(cls, raw: str) -> Self:
        database, value = raw.split(":", 1)
        return cls(database, value)

    def validate(self) -> list[ValidationErrorInfo]:
        if self.database not in self.VALID_PATTERNS.keys():
            return [
                ValidationErrorInfo(
                    "citation", f"Invalid database type {self.database!r}"
                )
            ]

        if not re.match(self.VALID_PATTERNS[self.database], self.value):
            return [
                ValidationErrorInfo(
                    "citation",
                    f"Invalid value {self.value!r} for database {self.database!r}",
                )
            ]
        return []

    def __lt__(self, other: Self) -> bool:
        return (self.database, self.value) < (other.database, other.value)

    def __hash__(self) -> int:
        return hash((self.database, self.value))


def validate_citation_list(
    citations: list[Citation],
    field: str | None = None,
    quality: QualityLevel | None = None,
) -> list[ValidationErrorInfo]:
    if field is None:
        field = "Citation"

    errors: list[ValidationErrorInfo] = []
    if quality is not QualityLevel.QUESTIONABLE and not citations:
        errors.append(
            ValidationErrorInfo(
                field, f"citation list cannot be empty at quality level {quality}"
            )
        )
    for citation in citations:
        errors.extend(citation.validate())
    return errors


@dataclass(frozen=True)
class SubmitterID:
    _inner: str
    _validate: InitVar[bool] = True

    def __post_init__(self, _validate: bool = True) -> None:
        if not _validate:
            return

        errors = self.validate()
        if errors:
            raise ValidationError(errors)

    def __lt__(self, other: Self) -> bool:
        return self._inner < other._inner

    def validate(self) -> list[ValidationErrorInfo]:
        if len(self._inner) != 24:
            return [ValidationErrorInfo("submitter", "invalid length")]

        if not self._inner.isalnum():
            return [ValidationErrorInfo("submitter", "invalid characters")]

        return []

    def __str__(self) -> str:
        return self._inner

    def to_json(self) -> str:
        return self._inner

    @classmethod
    def from_json(cls, raw: str) -> Self:
        return cls(raw)


class ReleaseEntry:
    contributors: list[SubmitterID]
    reviewers: list[SubmitterID]
    date: datetime.date
    comment: str

    def __init__(
        self,
        contributors: list[SubmitterID],
        reviewers: list[SubmitterID],
        date: datetime.date,
        comment: str,
        validate: bool = True,
    ) -> None:
        self.contributors = contributors
        self.reviewers = reviewers
        self.date = date
        self.comment = comment

        if not validate:
            return

        errors = self.validate()
        if errors:
            raise ValidationError(errors)

    def validate(self) -> list[ValidationErrorInfo]:
        errors: list[ValidationErrorInfo] = []
        if not self.contributors:
            errors.append(
                ValidationErrorInfo("contributors", "contributor list cannot be empty")
            )
        for contributor in self.contributors:
            errors.extend(contributor.validate())
        for reviewer in self.reviewers:
            errors.extend(reviewer.validate())

        return errors

    def __str__(self) -> str:
        return f"{self.date} {self.comment}, Contributors: {', '.join(str(c) for c in self.contributors)}; Reviewers: {', '.join(str(r) for r in self.reviewers)}"

    def to_json(self) -> dict[str, Any]:
        return {
            "contributors": [c.to_json() for c in self.contributors],
            "reviewers": [r.to_json() for r in self.reviewers],
            "date": self.date.strftime("%Y-%m-%d"),
            "comment": self.comment,
        }

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Self:
        contributors = [SubmitterID.from_json(c) for c in raw.get("contributors", [])]
        reviewers = [SubmitterID.from_json(r) for r in raw.get("reviewers", [])]
        date = datetime.datetime.strptime(raw["date"], "%Y-%m-%d")
        comment = raw["comment"]
        return cls(contributors, reviewers, date, comment)


class ReleaseVersion:
    _inner: str

    def __init__(self, value: str, validate: bool = True) -> None:
        self._inner = value

        if not validate:
            return

        errors = self.validate()
        if errors:
            raise ValidationError(errors)

    def validate(self) -> list[ValidationErrorInfo]:
        if self._inner == "next":
            return []

        for part in self._inner.split("."):
            if not part.isdigit():
                return [
                    ValidationErrorInfo(
                        "release version", f"invalid version {self._inner!r}"
                    )
                ]
        return []

    def __str__(self) -> str:
        return self._inner

    def to_json(self) -> str:
        return self._inner

    @classmethod
    def from_json(cls, raw: str) -> Self:
        return cls(raw)


class Release:
    version: ReleaseVersion
    date: datetime.date | None
    entries: list[ReleaseEntry]

    def __init__(
        self,
        version: ReleaseVersion,
        date: datetime.date | None,
        entries: list[ReleaseEntry],
        validate: bool = True,
    ) -> None:
        self.version = version
        self.date = date
        self.entries = entries

        if not validate:
            return

    def validate(self) -> list[ValidationErrorInfo]:
        errors: list[ValidationErrorInfo] = []

        errors.extend(self.version.validate())

        if self.date is None and str(self.version) != "next":
            errors.append(
                ValidationErrorInfo(
                    "Release", "Release date must be provided if version is not 'next'"
                )
            )

        for entry in self.entries:
            errors.extend(entry.validate())

        return errors

    def __str__(self) -> str:
        ret = f"{self.version} ({self.date})\n"
        for entry in self.entries:
            ret += f"  {entry}\n"

        return ret

    def to_json(self) -> dict[str, Any]:
        ret = {
            "version": self.version.to_json(),
            "entries": [e.to_json() for e in self.entries],
        }
        ret["date"] = self.date.strftime("%Y-%m-%d") if self.date else None
        return ret

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Self:
        version = ReleaseVersion.from_json(raw["version"])
        date = (
            datetime.datetime.strptime(raw["date"], "%Y-%m-%d") if raw["date"] else None
        )
        entries = [ReleaseEntry.from_json(e) for e in raw["entries"]]

        return cls(version, date, entries)


class ChangeLog:
    releases: list[Release]

    def __init__(self, releases: list[Release], validate: bool = True) -> None:
        self.releases = releases

        if not validate:
            return

        errors = self.validate()
        if errors:
            raise ValidationError(errors)

    def validate(self) -> list[ValidationErrorInfo]:
        errors: list[ValidationErrorInfo] = []

        for release in self.releases:
            errors.extend(release.validate())

        return errors

    def __str__(self) -> str:
        return "\n".join(str(r) for r in self.releases)

    def to_json(self) -> dict[str, Any]:
        return {"releases": [r.to_json() for r in self.releases]}

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Self:
        releases = [Release.from_json(r) for r in raw["releases"]]
        return cls(releases)


class Smiles:
    value: str

    def __init__(self, value: str, validate: bool = True) -> None:
        self.value = value

        if not validate:
            return

        errors = self.validate()
        if errors:
            raise ValidationError(errors)

    def validate(self) -> list[ValidationErrorInfo]:
        errors: list[ValidationErrorInfo] = []

        if not re.match(r"^[\[\]a-zA-Z0-9\@()=\/\\#+.%*-]+$", self.value):
            errors.append(
                ValidationErrorInfo("Smiles", f"Invalid value {self.value:r}")
            )

        return errors

    def __str__(self) -> str:
        return self.value

    @classmethod
    def from_json(cls, raw: str) -> Self:
        return cls(raw)

    def to_json(self) -> str:
        return self.value

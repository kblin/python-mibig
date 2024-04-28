from typing import Any, Self

from mibig.converters.shared.common import Citation, GeneId, Smiles, validate_citation_list
from mibig.errors import ValidationError, ValidationErrorInfo


class GTEvidence:
    method: str
    referemces: list[Citation]

    VALID_METHODS = (
        "Sequence-based prediction",
        "Structure-based inference",
        "Knock-out construct",
        "Activity assay",
    )

    def __init__(self, method: str, references: list[Citation], validate: bool = True) -> None:
        self.method = method
        self.references = references

        if not validate:
            return

        errors = self.validate()
        if errors:
            raise ValidationError(errors)

    def validate(self) -> list[ValidationErrorInfo]:
        errors = []

        if self.method not in self.VALID_METHODS:
            errors.append(ValidationErrorInfo("GTEvidence.method", f"Invalid method: {self.method}"))

        errors.extend(validate_citation_list(self.references))

        return errors

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> Self:
        return cls(
            method=raw["method"],
            references=[Citation.from_json(c) for c in raw.get("references", [])],
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "references": [c.to_json() for c in self.references],
        }


class Glycosyltransferase:
    gene: GeneId
    evidence: list[GTEvidence]
    specificity: Smiles | None

    def __init__(self, gene: GeneId, evidence: list[GTEvidence], specificity: Smiles | None, validate: bool = True, **kwargs) -> None:
        self.gene = gene
        self.evidence = evidence
        self.specificity = specificity

        if not validate:
            return

        errors = self.validate(**kwargs)
        if errors:
            raise ValidationError(errors)

    def validate(self, **kwargs) -> list[ValidationErrorInfo]:
        errors = []

        errors.extend(self.gene.validate(**kwargs))
        for evidence in self.evidence:
            errors.extend(evidence.validate())
        if self.specificity:
            errors.extend(self.specificity.validate())

        return errors

    @classmethod
    def from_json(cls, raw: dict[str, Any], **kwargs) -> Self:
        return cls(
            gene=GeneId.from_json(raw["gene"], **kwargs),
            evidence=[GTEvidence.from_json(e) for e in raw.get("evidence", [])],
            specificity=Smiles(raw["specificity"]) if "specificity" in raw else None,
        )

    def to_json(self) -> dict[str, Any]:
        ret = {
            "gene": self.gene.to_json(),
            "evidence": [e.to_json() for e in self.evidence],
        }
        if self.specificity:
            ret["specificity"] = self.specificity.to_json()

        return ret


class Subcluster:
    specificity: Smiles
    genes: list[GeneId]
    references: list[Citation]

    def __init__(self, specificity: Smiles, genes: list[GeneId], references: list[Citation], validate: bool = True, **kwargs) -> None:
        self.specificity = specificity
        self.genes = genes
        self.references = references

        if not validate:
            return

        errors = self.validate(**kwargs)
        if errors:
            raise ValidationError(errors)

    def validate(self, **kwargs) -> list[ValidationErrorInfo]:
        errors = []

        errors.extend(self.specificity.validate())
        for gene in self.genes:
            errors.extend(gene.validate(**kwargs))
        errors.extend(validate_citation_list(self.references))

        return errors

    @classmethod
    def from_json(cls, raw: dict[str, Any], **kwargs) -> Self:
        return cls(
            specificity=Smiles(raw["specificity"]),
            genes=[GeneId.from_json(gene, **kwargs) for gene in raw["genes"]],
            references=[Citation.from_json(c) for c in raw.get("references", [])],
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "specificity": self.specificity.to_json(),
            "genes": [gene.to_json() for gene in self.genes],
            "references": [c.to_json() for c in self.references],
        }


class Saccharide:
    subclass: str | None
    subclusters: list[Subcluster]
    glycosyltransferases: list[Glycosyltransferase]

    def __init__(self, subclusters: list[Subcluster], glycosyltransferases: list[Glycosyltransferase], subclass: str | None = None,
                 validate: bool = True, **kwargs) -> None:
        self.subclass = subclass
        self.subclusters = subclusters
        self.glycosyltransferases = glycosyltransferases

        if not validate:
            return

        errors = self.validate(**kwargs)
        if errors:
            raise ValidationError(errors)

    def validate(self, **kwargs) -> list[ValidationErrorInfo]:
        errors = []

        for subcluster in self.subclusters:
            errors.extend(subcluster.validate(**kwargs))
        for glycosyltransferase in self.glycosyltransferases:
            errors.extend(glycosyltransferase.validate(**kwargs))

        return errors

    @classmethod
    def from_json(cls, raw: dict[str, Any], **kwargs) -> Self:
        return cls(
            subclass=raw.get("subclass"),
            subclusters=[Subcluster.from_json(subcluster, **kwargs) for subcluster in raw["subclusters"]],
            glycosyltransferases=[Glycosyltransferase.from_json(glycosyltransferase, **kwargs) for glycosyltransferase in raw["glycosyltransferases"]],
        )

    def to_json(self) -> dict[str, Any]:
        ret: dict[str, Any] = {
            "glycosyltransferases": [glycosyltransferase.to_json() for glycosyltransferase in self.glycosyltransferases],
        }

        if self.subclass:
            ret["subclass"] = self.subclass

        if self.subclusters:
            ret["subclusters"] = [subcluster.to_json() for subcluster in self.subclusters]


        return ret
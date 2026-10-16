"""Dedicated Demo generation fencing and non-executable maintenance validation."""
import json
from pathlib import Path
import secrets

from django.conf import settings
from django.core import signing
from django.http import HttpResponse, JsonResponse
from django.utils.html import format_html

SESSION_KEY = "sales_ai_demo_generation"
PROOF_HEADER = "HTTP_X_DEMO_GENERATION_PROOF"
FORM_FIELD = "_demo_generation_proof"
CLIENT_PATH = "/__demo_infrastructure__/generation.js"
SALT = "sales-ai-demo.document-generation.v1"
PINNED = ("identity", "database", "database_oid", "host", "database_port", "container", "container_id",
          "volume", "owner_role", "runtime_role", "migration_fingerprint", "application_port")


class GenerationRefused(ValueError):
    pass


def require(value, message):
    if not value:
        raise GenerationRefused(message)


def initial_registry(profile):
    return dict(version=1, phase="ACTIVE", active_generation=profile["identity"],
                pinned={key: profile[key] for key in PINNED}, maintenance=None,
                previous_healthy_generations=[])


def validate_registry(value, pinned_profile, live_profile):
    require(value.get("version") == 1 and value.get("phase") == "ACTIVE" and value.get("maintenance") is None,
            "Maintenance state is incomplete or uncertain.")
    expected = {key: pinned_profile[key] for key in PINNED}
    require(value.get("pinned") == expected and all(live_profile.get(k) == v for k,v in expected.items()),
            "Generation database/container/endpoint binding changed.")
    require(value.get("active_generation") == pinned_profile["identity"], "Active generation changed.")
    return value["active_generation"]


def active_generation():
    config = settings.DEMO_GENERATION_CONFIG
    state = Path(config["state"])
    try:
        registry = json.loads((state / "generation-state.json").read_text(encoding="utf-8"))
        profile = json.loads((state / "profile.json").read_text(encoding="utf-8"))
        return validate_registry(registry, config["profile"], profile)
    except (OSError, ValueError, KeyError, TypeError):
        raise GenerationRefused("Protected generation state is missing, changed or uncertain.") from None


def document_proof(generation):
    return signing.dumps(dict(version=1,generation=generation,document=secrets.token_urlsafe(12)),salt=SALT)


def verify_proof(proof, generation):
    try:
        require(isinstance(proof,str) and 0 < len(proof) < 2048, "Missing generation proof.")
        value=signing.loads(proof,salt=SALT)
        require(value.get("version")==1 and value.get("generation")==generation and bool(value.get("document")),
                "Stale document or command generation.")
    except (signing.BadSignature, ValueError, AttributeError, TypeError):
        raise GenerationRefused("Invalid or stale generation proof.") from None


def bind_login(sender, request, user, **kwargs):
    request.session[SESSION_KEY] = active_generation()


def install(profile, state):
    # Called only by the dedicated Demo runtime configuration, never base settings.
    settings.DEMO_GENERATION_CONFIG = dict(profile=dict(profile),state=str(state))
    active_generation()  # Missing/partial registry fails before serving.
    middleware = "scripts.demo.generation.DemoGenerationMiddleware"
    chain=list(settings.MIDDLEWARE)
    if middleware not in chain:
        chain.insert(chain.index("django.contrib.auth.middleware.AuthenticationMiddleware")+1,middleware)
    settings.MIDDLEWARE=chain
    from scripts.demo.maintenance_gate import install as install_maintenance
    install_maintenance(profile)
    from django.contrib.auth.signals import user_logged_in
    user_logged_in.connect(bind_login,dispatch_uid="sales-ai-demo-generation-binding",weak=False)


class DemoGenerationMiddleware:
    def __init__(self,get_response):self.get_response=get_response

    def __call__(self,request):
        try:generation=active_generation()
        except GenerationRefused:
            return self.denied("DEMO_MAINTENANCE_UNCERTAIN",503)
        if request.path==CLIENT_PATH and request.method in {"GET","HEAD"}:
            response=HttpResponse(Path(__file__).with_name("generation_client.js").read_text(encoding="utf-8"),content_type="application/javascript")
            response["Cache-Control"]="no-store"
            return response
        login=request.path=="/accounts/login/"
        if getattr(request.user,"is_authenticated",False) and not login and request.session.get(SESSION_KEY)!=generation:
            return self.denied("DEMO_SESSION_STALE",403)
        if request.method not in {"GET","HEAD","OPTIONS"}:
            # Every unsafe Demo request, including login, retains ordinary CSRF.
            proof=request.META.get(PROOF_HEADER)
            if proof is None and request.content_type in {"application/x-www-form-urlencoded","multipart/form-data"}:
                proof=request.POST.get(FORM_FIELD)
                if FORM_FIELD in request.POST:
                    fields=request.POST.copy();fields.pop(FORM_FIELD,None);request.POST=fields
            try:verify_proof(proof,generation)
            except GenerationRefused:return self.denied("DEMO_COMMAND_GENERATION_STALE",409)
        response=self.get_response(request)
        if not response.streaming and "text/html" in response.get("Content-Type",""):
            # Head-only transport bootstrap: no visible UI/layout modification.
            tag=format_html('<script src="{}" data-demo-generation="{}" data-demo-proof="{}"></script>',
                            CLIENT_PATH,generation,document_proof(generation))
            html=response.content.decode(response.charset)
            if "</head>" in html:
                response.content=html.replace("</head>",str(tag)+"</head>",1).encode(response.charset)
                response["Content-Length"]=str(len(response.content));response["Cache-Control"]="private, no-store"
        return response

    @staticmethod
    def denied(code,status):
        response=JsonResponse(dict(code=code,detail="نسل محیط نمایشی معتبر نیست؛ از راه‌انداز معتبر وارد شوید و فرمان قبلی را دوباره ارسال نکنید."),status=status)
        response["Cache-Control"]="no-store"
        return response


PHASES=("PLANNED","CANDIDATE_VALIDATED","RECOVERY_RECORDED","OLD_APP_QUIESCED",
        "OLD_WRITES_FENCED","PROFILE_SELECTED","NEW_APP_VALIDATED","COMPLETE")


def validate_journal(entries,old_generation,candidate_generation):
    """Pure journal validator; neither advances a journal nor performs promotion."""
    import hashlib
    from uuid import UUID
    require(str(UUID(old_generation))==old_generation and str(UUID(candidate_generation))==candidate_generation,
            "Journal requires exact canonical generation UUIDs.")
    require(old_generation!=candidate_generation,"Candidate must be independent.")
    previous=None
    required={"CANDIDATE_VALIDATED":{"exact_identity","independent_validation","owner_approval"},
              "RECOVERY_RECORDED":{"old_profile","old_identity","retained_healthy_generation","rollback_grants"},
              "OLD_APP_QUIESCED":{"verified_process","drained_requests"},
              "OLD_WRITES_FENCED":{"verified_old_role_fence"},
              "PROFILE_SELECTED":{"recorded_profile_selection"},
              "NEW_APP_VALIDATED":{"normal_auth","generation_fence","read_only_reconciliation"},
              "COMPLETE":{"explicit_activation_approval","previous_healthy_retained"}}
    for i,entry in enumerate(entries):
        require(i<len(PHASES) and entry.get("phase")==PHASES[i] and entry.get("sequence")==i,
                "Missing, reordered or duplicate maintenance phase.")
        require(entry.get("old_generation")==old_generation and entry.get("candidate_generation")==candidate_generation
                and entry.get("previous_sha256")==previous,"Journal identity/hash-chain mismatch.")
        require(required.get(entry["phase"],set()) <= set(entry.get("evidence",{}))
                and all(entry["evidence"].get(k) is True for k in required.get(entry["phase"],set())),
                "Missing validated phase evidence.")
        if entry["phase"] in {"RECOVERY_RECORDED","COMPLETE"}:
            retained=entry.get("evidence",{}).get("retained_healthy_generations",[])
            require(isinstance(retained,list) and old_generation in retained,
                    "At least the previous healthy generation must remain retained.")
        body={k:v for k,v in entry.items() if k!="sha256"}
        expected=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=True).encode()).hexdigest()
        require(entry.get("sha256")==expected,"Journal entry checksum mismatch.")
        previous=expected
    return dict(execution_available=False,multi_step_atomic=False,last_phase=entries[-1]["phase"] if entries else None,
                mutations_allowed=False,recovery="Fail closed; inspect both exact identities, last durable phase and profiles. Never auto-resume/switch/cleanup.",
                activation_complete_evidence=bool(entries) and entries[-1]["phase"]=="COMPLETE")

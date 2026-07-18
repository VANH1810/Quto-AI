"use client";

import { AlertCircle, CheckCircle2, LoaderCircle, MapPin, Siren, X } from "lucide-react";
import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SIN_THAU_COMMUNE, useSharedLocation } from "@/contexts/LocationContext";
import { DataGatewayError } from "@/services/dataGatewayClient";
import { submitSos } from "@/services/sos-service";
import type { SOSRequestType, SOSSubmission } from "@/types/sos";

const COOLDOWN_SECONDS = 600;
const COOLDOWN_UNTIL_KEY = "dien-bien-sos-cooldown-until";
const LAST_FINGERPRINT_KEY = "dien-bien-sos-last-fingerprint";
const DEVICE_ID_KEY = "dien-bien-sos-device-id";

const REQUEST_TYPES: Array<{ value: SOSRequestType; label: string }> = [
  { value: "flood_trapped", label: "Mắc kẹt do lũ" },
  { value: "landslide_buried", label: "Sạt lở, vùi lấp" },
  { value: "injured", label: "Có người bị thương" },
  { value: "isolated", label: "Bị cô lập, mất đường" },
  { value: "missing", label: "Có người mất tích" },
  { value: "other", label: "Yêu cầu khẩn cấp khác" },
];

interface EmergencySOSProps {
  commune?: { code: string; name: string } | null;
  userInfo?: { fullName?: string; phone?: string; cccd?: string };
}

function getOrCreateDeviceId() {
  const stored = window.localStorage.getItem(DEVICE_ID_KEY);
  if (stored) return stored;
  const id = window.crypto?.randomUUID?.() ?? `device-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  window.localStorage.setItem(DEVICE_ID_KEY, id);
  return id;
}

function formatCountdown(seconds: number) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const remainder = (seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainder}`;
}

function requestFingerprint(payload: SOSSubmission) {
  return [
    payload.lat.toFixed(5),
    payload.lon.toFixed(5),
    payload.danger_type,
    payload.num_people,
    payload.note?.trim().toLocaleLowerCase("vi") ?? "",
  ].join("|");
}

export const EmergencySOS = memo(function EmergencySOS({ commune, userInfo }: EmergencySOSProps) {
  const { position, isLocating, locationSource } = useSharedLocation();
  const [dialog, setDialog] = useState<"closed" | "confirm" | "success">("closed");
  const [isSending, setIsSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [cooldownUntil, setCooldownUntil] = useState(0);
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const stored = Number(window.localStorage.getItem(COOLDOWN_UNTIL_KEY) ?? 0);
    if (Number.isFinite(stored) && stored > Date.now()) setCooldownUntil(stored);
  }, []);

  useEffect(() => {
    if (!cooldownUntil) {
      setRemainingSeconds(0);
      return;
    }
    const update = () => {
      const remaining = Math.max(0, Math.ceil((cooldownUntil - Date.now()) / 1000));
      setRemainingSeconds(remaining);
      if (remaining === 0) {
        window.localStorage.removeItem(COOLDOWN_UNTIL_KEY);
        setCooldownUntil(0);
      }
    };
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [cooldownUntil]);

  useEffect(() => {
    if (dialog === "closed") return;
    if (dialog === "confirm") closeButtonRef.current?.focus();
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isSending) setDialog("closed");
    };
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [dialog, isSending]);

  const resolvedCommune = useMemo(
    () => commune ?? (locationSource === "mock" ? SIN_THAU_COMMUNE : null),
    [commune, locationSource],
  );

  const openConfirmation = useCallback(() => {
    if (!position || isLocating || isSending || remainingSeconds > 0) return;
    setErrorMessage(null);
    setDialog("confirm");
  }, [isLocating, isSending, position, remainingSeconds]);

  const closeDialog = useCallback(() => {
    if (!isSending) setDialog("closed");
  }, [isSending]);

  const sendSignal = useCallback(async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!position) {
      setErrorMessage("Chưa có tọa độ để gửi tín hiệu. Vui lòng chờ hệ thống xác định vị trí.");
      return;
    }

    const formData = new FormData(event.currentTarget);
    const requestType = formData.get("request_type") as SOSRequestType;
    const peopleCount = Number(formData.get("num_people")) || 1;
    const fullName = String(formData.get("full_name") ?? "").trim();
    const phone = String(formData.get("phone") ?? "").trim();
    const cccd = String(formData.get("cccd") ?? "").trim();
    const note = String(formData.get("note") ?? "").trim();

    const payload: SOSSubmission = {
      lat: position.lat,
      lon: position.lon,
      danger_type: requestType,
      num_people: Math.max(1, Math.min(99, peopleCount)),
      reported_at: new Date().toISOString(),
      full_name: fullName || undefined,
      phone: phone || undefined,
      cccd: cccd || undefined,
      note: note || undefined,
      commune_code: resolvedCommune?.code,
      commune_name: resolvedCommune?.name,
    };
    const fingerprint = requestFingerprint(payload);
    const storedFingerprint = window.localStorage.getItem(LAST_FINGERPRINT_KEY);
    const storedCooldown = Number(window.localStorage.getItem(COOLDOWN_UNTIL_KEY) ?? 0);
    if (storedFingerprint === fingerprint && storedCooldown > Date.now()) {
      setErrorMessage("Tín hiệu trùng tọa độ và nội dung đang trong thời gian chờ. Vui lòng không gửi lại.");
      setCooldownUntil(storedCooldown);
      return;
    }

    setIsSending(true);
    setErrorMessage(null);
    try {
      await submitSos(payload, getOrCreateDeviceId());
      const nextCooldown = Date.now() + COOLDOWN_SECONDS * 1000;
      window.localStorage.setItem(COOLDOWN_UNTIL_KEY, String(nextCooldown));
      window.localStorage.setItem(LAST_FINGERPRINT_KEY, fingerprint);
      setCooldownUntil(nextCooldown);
      setDialog("success");
    } catch (error) {
      if (error instanceof DataGatewayError) {
        if (error.status === 429) {
          const retryAfter = Math.max(1, error.retryAfterSeconds ?? COOLDOWN_SECONDS);
          const nextCooldown = Date.now() + retryAfter * 1000;
          window.localStorage.setItem(COOLDOWN_UNTIL_KEY, String(nextCooldown));
          setCooldownUntil(nextCooldown);
        }
        setErrorMessage(error.message);
      } else {
        setErrorMessage(error instanceof Error && error.message.includes("API cứu hộ")
          ? error.message
          : "Không thể kết nối đến API cứu hộ/UBND. Tín hiệu chưa được xác nhận; vui lòng thử lại.");
      }
    } finally {
      setIsSending(false);
    }
  }, [position, resolvedCommune]);

  const buttonLabel = isLocating
    ? "Đang lấy vị trí…"
    : isSending
      ? "Đang gửi SOS…"
      : remainingSeconds > 0
        ? `SOS ${formatCountdown(remainingSeconds)}`
        : "SOS khẩn cấp";

  return (
    <>
      <button
        className="sos-header-button"
        type="button"
        onClick={openConfirmation}
        disabled={!position || isLocating || isSending || remainingSeconds > 0}
        aria-label={remainingSeconds > 0 ? `SOS đang khóa, còn ${formatCountdown(remainingSeconds)}` : buttonLabel}
      >
        {isSending || isLocating ? <LoaderCircle className="spin" aria-hidden="true" /> : <Siren aria-hidden="true" />}
        <span>{buttonLabel}</span>
      </button>

      {dialog === "confirm" && (
        <div className="sos-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeDialog(); }}>
          <section className="sos-dialog" role="dialog" aria-modal="true" aria-labelledby="sos-confirm-title" aria-describedby="sos-confirm-description">
            <header>
              <span className="sos-dialog-icon"><Siren aria-hidden="true" /></span>
              <div><small>Gửi đến UBND và bộ phận cứu hộ</small><h2 id="sos-confirm-title">Xác nhận gửi tín hiệu cầu cứu?</h2></div>
              <button ref={closeButtonRef} className="sos-dialog-close" type="button" onClick={closeDialog} disabled={isSending} aria-label="Đóng hộp xác nhận"><X aria-hidden="true" /></button>
            </header>
            <form onSubmit={sendSignal}>
              <p id="sos-confirm-description" className="sos-dialog-intro">Chỉ gửi khi bạn hoặc người xung quanh đang cần hỗ trợ khẩn cấp.</p>

              <div className="sos-location-status">
                <MapPin aria-hidden="true" />
                <span><strong>{resolvedCommune?.name ?? "Đang xác định xã/phường từ tọa độ"}</strong><small>{position?.lat.toFixed(6)}, {position?.lon.toFixed(6)}</small></span>
              </div>
              <div className="sos-form-grid">
                <label className="sos-field sos-field-wide"><span>Loại yêu cầu</span><select name="request_type" defaultValue="other">{REQUEST_TYPES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
                <label className="sos-field"><span>Số người cần hỗ trợ</span><input name="num_people" type="number" min="1" max="99" inputMode="numeric" defaultValue="1" /></label>
                <label className="sos-field"><span>Họ tên (nếu có)</span><input name="full_name" defaultValue={userInfo?.fullName ?? ""} autoComplete="name" maxLength={100} /></label>
                <label className="sos-field"><span>Số điện thoại (nếu có)</span><input name="phone" defaultValue={userInfo?.phone ?? ""} type="tel" autoComplete="tel" maxLength={20} /></label>
                <label className="sos-field"><span>CCCD (nếu có)</span><input name="cccd" defaultValue={userInfo?.cccd ?? ""} inputMode="numeric" autoComplete="off" maxLength={20} /></label>
                <label className="sos-field sos-field-wide"><span>Mô tả tình huống</span><textarea name="note" rows={3} maxLength={500} placeholder="Ví dụ: mắc kẹt trên mái nhà, có người bị thương…" /></label>
              </div>

              {errorMessage && <p className="sos-submit-error" role="alert"><AlertCircle aria-hidden="true" />{errorMessage}</p>}
              <footer><button type="button" className="sos-cancel-button" onClick={closeDialog} disabled={isSending}>Hủy</button><button type="submit" className="sos-confirm-button" disabled={isSending}>{isSending ? <><LoaderCircle className="spin" aria-hidden="true" />Đang gửi…</> : <><Siren aria-hidden="true" />Xác nhận gửi SOS</>}</button></footer>
            </form>
          </section>
        </div>
      )}

      {dialog === "success" && (
        <div className="sos-dialog-backdrop" role="presentation">
          <section className="sos-dialog sos-success-dialog" role="dialog" aria-modal="true" aria-labelledby="sos-success-title">
            <span className="sos-success-icon"><CheckCircle2 aria-hidden="true" /></span>
            <h2 id="sos-success-title">Đã gửi tín hiệu cầu cứu thành công.</h2>
            <p>UBND và bộ phận cứu hộ đã nhận được tọa độ của bạn.</p>
            <button type="button" onClick={closeDialog}>Đóng</button>
          </section>
        </div>
      )}
    </>
  );
});

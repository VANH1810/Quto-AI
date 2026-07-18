"use client";

import Image from "next/image";
import { memo, useEffect, useId, useMemo, useRef, useState } from "react";
import { ChevronDown, LocateFixed, MapPinned } from "lucide-react";
import type { CommuneAlert, CommuneCenter } from "@/types";
import { RISK_META } from "@/utils/risk";

interface CommuneLocationPickerProps {
  communes: CommuneCenter[];
  alerts: CommuneAlert[];
  query: string;
  isLocating: boolean;
  locationError: string | null;
  hasUserPosition: boolean;
  selectedCommuneCode?: string;
  className?: string;
  label?: string;
  onQueryChange: (value: string) => void;
  onSelectCommune: (code: string) => void;
  onClearCommune: () => void;
  onLocate: () => void;
}

export const CommuneLocationPicker = memo(function CommuneLocationPicker({
  communes,
  alerts,
  query,
  isLocating,
  locationError,
  hasUserPosition,
  selectedCommuneCode,
  className = "",
  label = "Vị trí tại Điện Biên",
  onQueryChange,
  onSelectCommune,
  onClearCommune,
  onLocate,
}: CommuneLocationPickerProps) {
  const instanceId = useId();
  const listboxId = `commune-options-${instanceId}`;
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const blurTimeoutRef = useRef<number | null>(null);
  const normalized = query.trim().toLocaleLowerCase("vi");
  const alertsByCommune = useMemo(() => new Map(alerts.map((alert) => [alert.communeCode, alert])), [alerts]);
  const selectedCommune = useMemo(
    () => communes.find((commune) => commune.code === selectedCommuneCode),
    [communes, selectedCommuneCode],
  );
  const selectedNameIsShown = selectedCommune?.name === query;
  const visibleCommunes = useMemo(
    () => selectedNameIsShown
      ? communes
      : communes.filter((commune) => !normalized || `${commune.name} ${commune.district}`.toLocaleLowerCase("vi").includes(normalized)),
    [communes, normalized, selectedNameIsShown],
  );

  useEffect(() => () => {
    if (blurTimeoutRef.current !== null) window.clearTimeout(blurTimeoutRef.current);
  }, []);

  function selectCommune(commune: CommuneCenter) {
    onSelectCommune(commune.code);
    setIsOpen(false);
    setActiveIndex(0);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setIsOpen(true);
      setActiveIndex((index) => Math.min(index + 1, Math.max(visibleCommunes.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setIsOpen(true);
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter" && isOpen && visibleCommunes[activeIndex]) {
      event.preventDefault();
      selectCommune(visibleCommunes[activeIndex]);
    } else if (event.key === "Escape") {
      setIsOpen(false);
    }
  }

  return (
    <div className={`commune-picker ${className}`.trim()}>
      <div className="commune-combobox">
        <span className="field-label">{label}</span>
        <div className={isOpen ? "search-box open" : "search-box"}>
          <Image className="figma-search-icon" src="/figma/search.svg" width={25} height={25} alt="" aria-hidden="true" />
          <input
            role="combobox"
            aria-label="Chọn xã hoặc phường"
            aria-autocomplete="list"
            aria-expanded={isOpen}
            aria-controls={listboxId}
            aria-activedescendant={isOpen && visibleCommunes[activeIndex] ? `${listboxId}-${visibleCommunes[activeIndex].code}` : undefined}
            value={query}
            onFocus={() => {
              if (blurTimeoutRef.current !== null) window.clearTimeout(blurTimeoutRef.current);
              setIsOpen(true);
            }}
            onBlur={() => {
              blurTimeoutRef.current = window.setTimeout(() => setIsOpen(false), 0);
            }}
            onChange={(event) => {
              onQueryChange(event.target.value);
              setActiveIndex(0);
              setIsOpen(true);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Chọn xã/phường..."
          />
          {query ? (
            <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={() => { onClearCommune(); setIsOpen(true); }} aria-label="Xóa xã phường đã chọn">×</button>
          ) : (
            <button type="button" className="dropdown-toggle" onMouseDown={(event) => event.preventDefault()} onClick={() => setIsOpen((open) => !open)} aria-label="Mở danh sách xã phường"><ChevronDown size={17} /></button>
          )}
        </div>

        {isOpen && (
          <div id={listboxId} className="commune-options" role="listbox" aria-label="Danh sách xã phường Điện Biên">
            <div className="commune-options-meta"><span>{visibleCommunes.length} xã/phường</span><small>Gõ tên để lọc</small></div>
            {visibleCommunes.map((commune, index) => {
              const alert = alertsByCommune.get(commune.code);
              const risk = alert ? RISK_META[alert.riskLevel] : null;
              const selected = commune.code === selectedCommuneCode;
              return (
                <button
                  type="button"
                  id={`${listboxId}-${commune.code}`}
                  role="option"
                  aria-selected={selected}
                  key={commune.code}
                  className={`${selected ? "selected " : ""}${index === activeIndex ? "active" : ""}`.trim()}
                  onMouseDown={(event) => event.preventDefault()}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => selectCommune(commune)}
                >
                  <span className="option-risk" style={{ background: risk?.color ?? "#94a3b8" }} />
                  <span className="option-copy"><strong>{commune.name}</strong><small>{alert?.hazardLabel ?? commune.district}</small></span>
                  {alert && <span className="risk-pill" style={{ color: risk?.color, background: `${risk?.color}18` }}>Cấp {alert.riskLevel}</span>}
                </button>
              );
            })}
            {!visibleCommunes.length && <p className="empty-list">Không tìm thấy xã/phường phù hợp.</p>}
          </div>
        )}

        {selectedCommune && !hasUserPosition && (
          <p className="approximate-location"><MapPinned size={15} /><span><strong>Vị trí gần đúng</strong>Đang dùng {selectedCommune.name} để hiển thị khu vực của bạn.</span></p>
        )}
      </div>

      <button className="locate-button" type="button" onClick={onLocate} disabled={isLocating}>
        <LocateFixed size={18} className={isLocating ? "spin" : ""} />
        <span>{isLocating ? "Đang xác định vị trí..." : hasUserPosition ? "Đã dùng vị trí chính xác" : "Dùng vị trí hiện tại của tôi"}</span>
      </button>
      {locationError && <p className="inline-error">{locationError} Bạn có thể chọn xã/phường ở phía trên.</p>}
    </div>
  );
});

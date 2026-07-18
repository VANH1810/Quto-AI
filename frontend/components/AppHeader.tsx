"use client";

import Image from "next/image";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { memo, useState } from "react";
import { EmergencySOS } from "@/components/EmergencySOS";

interface AppHeaderProps {
  activePage?: "map" | "forecast";
  sosCommune?: { code: string; name: string } | null;
}

export const AppHeader = memo(function AppHeader({ activePage = "map", sosCommune }: AppHeaderProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <header className="app-header">
      <Link className="brand-home" href="/" aria-label="Về bản đồ cảnh báo" onClick={() => setMenuOpen(false)}>
        <Image className="brand-mark" src="/figma/dien-bien-science-logo.png" width={99} height={99} priority alt="Biểu trưng Bộ Khoa học và Công nghệ" />
      </Link>
      <div className="brand-copy">
        <span>Sở Khoa học &amp; Công nghệ Điện Biên</span>
        <strong>Cảnh báo thiên tai tỉnh Điện Biên</strong>
      </div>
      <button
        className="nav-toggle"
        type="button"
        aria-expanded={menuOpen}
        aria-controls="primary-navigation"
        aria-label={menuOpen ? "Đóng menu điều hướng" : "Mở menu điều hướng"}
        onClick={() => setMenuOpen((isOpen) => !isOpen)}
      >
        {menuOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
      </button>
      <nav id="primary-navigation" className={`primary-nav${menuOpen ? " open" : ""}`} aria-label="Điều hướng chính">
        <Link className={activePage === "map" ? "active" : undefined} href="/" aria-current={activePage === "map" ? "page" : undefined} onClick={() => setMenuOpen(false)}>Bản đồ cảnh báo</Link>
        <Link className={activePage === "forecast" ? "active" : undefined} href="/forecast" aria-current={activePage === "forecast" ? "page" : undefined} onClick={() => setMenuOpen(false)}>Dự báo khu vực</Link>
        <Link href="/admin" onClick={() => setMenuOpen(false)}>Quản trị</Link>
      </nav>
      <EmergencySOS commune={sosCommune} />
    </header>
  );
});

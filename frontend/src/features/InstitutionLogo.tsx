import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api";
import { useSession } from "../store";
import { useTranslation } from "react-i18next";
export default function InstitutionLogo() {
  const { t } = useTranslation();
  const member = useSession((s) => s.membership);
  const [url, setUrl] = useState("");
  const query = useQuery({
    queryKey: ["logo", member?.id],
    queryFn: () => api<Blob>("/institution/logo/", { blob: true }),
    enabled: !!member,
    retry: false,
    staleTime: 300000,
  });
  useEffect(() => {
    if (!query.data) return;
    const value = URL.createObjectURL(query.data);
    setUrl(value);
    return () => URL.revokeObjectURL(value);
  }, [query.data]);
  return url ? (
    <img
      src={url}
      width={44}
      height={44}
      alt={t("institutionLogo")}
      loading="lazy"
      style={{ objectFit: "contain" }}
    />
  ) : null;
}

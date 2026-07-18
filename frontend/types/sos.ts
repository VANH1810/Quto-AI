export type SOSStatus = "NEW" | "ACKNOWLEDGED" | "DISPATCHED" | "RESCUED" | "CANCELLED";
export type CommuneMappingStatus = "MAPPED" | "UNMAPPED" | "MANUALLY_CONFIRMED";

export type SOSRequestType =
  | "flood_trapped"
  | "landslide_buried"
  | "injured"
  | "isolated"
  | "missing"
  | "other";

export interface SOSSubmission {
  lat: number;
  lon: number;
  danger_type: SOSRequestType;
  num_people: number;
  reported_at: string;
  full_name?: string;
  phone?: string;
  cccd?: string;
  note?: string;
  commune_code?: string;
  commune_name?: string;
}

export interface SOSSubmissionResult {
  id: string;
  status: string;
  commune_code?: string | null;
  commune_name?: string | null;
  created_at: string;
}

export interface SOSRequest {
  id: string;
  reporterName?: string;
  reporterPhone?: string;
  latitude: number;
  longitude: number;
  accuracyMeters?: number;
  communeId?: string;
  communeName?: string;
  districtName?: string;
  mappingStatus: CommuneMappingStatus;
  peopleCount: number;
  description: string;
  status: SOSStatus;
  createdAt: string;
  acknowledgedAt?: string;
  dispatchedAt?: string;
  resolvedAt?: string;
  isDemo?: boolean;
  audit?: Array<{ step: string; detail: string }>;
}

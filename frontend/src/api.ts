import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

const client = axios.create({
  baseURL: API_BASE_URL,
});

const toAbsoluteUrl = (path: string) => {
  if (!path) return path;
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  const base = API_BASE_URL.replace(/\/$/, '');
  const suffix = path.startsWith('/') ? path : `/${path}`;
  return `${base}${suffix}`;
};

export interface BoundingBox {
  top: number;
  right: number;
  bottom: number;
  left: number;
}

export interface FaceSnapshot {
  bounding_box: BoundingBox;
  distance?: number;
  person_id?: string;
}

export interface MatchResult {
  photo_id: string;
  media_url: string;
  distance?: number | null;
  labels: string[];
  matched_face: FaceSnapshot;
  person_id?: string;
}

export interface SearchResponse {
  query_faces: number;
  matches: MatchResult[];
  report_url?: string | null;
}

const mapError = (error: unknown): never => {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (detail) {
      throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
    }
  }
  throw new Error('Unexpected server error. Check backend logs.');
};

export const searchFaces = async (file: File): Promise<SearchResponse> => {
  const form = new FormData();
  form.append('file', file);
  try {
    const { data } = await client.post<SearchResponse>('/api/v1/search', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return {
      query_faces: data.query_faces,
      matches: data.matches.map((match) => ({
        ...match,
        media_url: toAbsoluteUrl(match.media_url),
      })),
      report_url: data.report_url ? toAbsoluteUrl(data.report_url) : null,
    };
  } catch (error) {
    return mapError(error);
  }
};

const MLB_API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL
  ? `${process.env.NEXT_PUBLIC_API_BASE_URL}/mlb`
  : "http://localhost:8000/api/mlb";

export { MLB_API_BASE };

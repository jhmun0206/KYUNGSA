// FastAPI /api/v1/* 응답 스키마와 1:1 대응

export type Grade = "A" | "B" | "C" | "D"

export interface AuctionListItem {
  case_number: string
  address: string
  property_type: string
  court: string
  court_office_code: string
  appraised_value: number | null
  minimum_bid: number | null
  auction_date: string | null   // ISO 날짜 "2026-03-05"
  bid_count: number
  status: string

  // 점수
  grade: string | null
  total_score: number | null
  score_coverage: number | null
  grade_provisional: boolean
  predicted_winning_ratio: number | null

  // pillar 점수 (리스크 요약 표시용)
  price_score: number | null
  location_score: number | null
  occupancy_score: number | null

  // 좌표
  lat: number | null
  lng: number | null
}

export interface AuctionListResponse {
  total: number
  page: number
  size: number
  items: AuctionListItem[]
}

export interface ScoreDetail {
  total_score: number | null
  grade: string | null
  score_coverage: number | null
  grade_provisional: boolean
  property_category: string | null

  legal_score: number | null
  price_score: number | null
  location_score: number | null
  occupancy_score: number | null

  predicted_winning_ratio: number | null
  prediction_method: string | null

  sub_scores: Record<string, unknown> | null
  missing_pillars: string[]
  warnings: string[]
  needs_expert_review: boolean
}

export interface RoundItem {
  round_number: number
  round_date: string | null
  minimum_bid: number
  result: string
}

// ML 예측 관련
export interface MLPredictionFactor {
  feature: string       // "할인율 64%", "유찰 2회" 등 (사람 읽기용)
  importance: number    // 중요도 (%)
}

export interface MLPrediction {
  predicted_ratio: number | null
  predicted_price: number | null
  confidence: "high" | "medium" | "low"
  model_version: string               // "ml_v1" | "rule_v1"
  top_factors: MLPredictionFactor[]
  fallback_reason: string | null
}

export interface AuctionDetailResponse {
  case_number: string
  address: string
  property_type: string
  court: string
  court_office_code: string
  appraised_value: number | null
  minimum_bid: number | null
  auction_date: string | null
  bid_count: number
  status: string

  winning_bid: number | null
  winning_ratio: number | null
  winning_date: string | null

  lat: number | null
  lng: number | null

  score: ScoreDetail | null
  rounds: RoundItem[]

  // ML 낙찰가율 예측 (모델 있으면 ml_v1, 없으면 rule_v1 fallback)
  ml_prediction: MLPrediction | null

  specification_remarks: string
  building_info: BuildingInfo | null
  market_price_info: Record<string, unknown> | null
  location_data: Record<string, unknown> | null
}

export interface BuildingInfo {
  main_purpose: string
  structure: string
  total_area: number | null
  exclusive_area_m2: number | null
  ground_floors: number | null
  underground_floors: number | null
  units_count: number | null
  build_year: number | null
  use_approve_date: string
  violation: boolean
}

export interface MapItem {
  case_number: string
  lat: number
  lng: number
  grade: string | null
  address: string
  appraised_value: number | null
  auction_date: string | null
  property_type: string
}

export interface MapResponse {
  items: MapItem[]
}

// 필터 파라미터
export interface AuctionListParams {
  court_office_code?: string
  grade?: string        // "A,B,C"
  property_type?: string
  q?: string            // 주소 키워드 검색
  sort?: string
  page?: number
  size?: number
}

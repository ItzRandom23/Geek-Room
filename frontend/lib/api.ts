export const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

export type Session = { id:number; name:string; driver_name:string; circuit_name:string; created_at:string; status:string; is_demo:boolean; organization_id:number|null; analysis_mode:string|null; active_clip_id:number|null; audio_count:number; lap_count:number; audio?:AudioClip[]; laps?:Lap[]; transcript?:Transcript[]; emotions?:Emotion[]; insights?:Insight[]; report?:Report|null };
export type AudioClip = { id:number; original_filename:string; duration_seconds:number|null; detected_language?:string|null; sample_rate?:number|null; processing_status?:string; active?:boolean; uploaded_at:string };
export type Lap = { id:number; lap_number:number; lap_time_seconds:number; start_timestamp_seconds:number; end_timestamp_seconds:number };
export type Transcript = { id:number; start_seconds:number; end_seconds:number; text:string };
export type Emotion = { id:number; normalized_label:string; raw_label:string; confidence:number; source:string; start_seconds:number; end_seconds:number };
export type Insight = { id:number; type:string; severity:string; title:string; explanation:string; recommendation:string; supporting_data:Record<string,unknown> };
export type TimelineEvent = { timestamp:number; label:string; confidence:number; transcript:string; lap_number:number|null; recommendation:string|null };
export type Report = { primary_state:string; confidence:number; transcript:string; correlations:Record<string,unknown>[]; performance_by_state:{label:string;event_count:number;average_lap_time:number|null;delta_to_median:number|null}[]; recommendations:Insight[]; analysis_mode?:string; correlation_available?:boolean; association_notice?:string; provenance?:{models:Record<string,string>;language:string;generated_at:string;analysis_version:string;model_version?:string|null;validation_accuracy?:number|null;confidence_threshold?:number|null;prediction_coverage?:number|null;processing_time_ms?:number|null} };
export type AnalysisJob = { job_id:string; session_id:number; mode:string; status:string; phase:string; progress:number; attempts:number; retryable:boolean; error:{code:string;message:string;retryable:boolean}|null; report?:Report; created_at:string; started_at:string|null; completed_at:string|null };
export type AuthResponse = { access_token:string; token_type:string; user:{id:number;email:string;full_name:string}; organization:{id:number;name:string;role:string} };

export class ApiError extends Error { code:string; retryable:boolean; status:number; requestId?:string; constructor(message:string, code="REQUEST_FAILED", retryable=false, status=0, requestId?:string){super(message);this.name="ApiError";this.code=code;this.retryable=retryable;this.status=status;this.requestId=requestId;} }
export function getToken(){return typeof window === "undefined" ? null : window.localStorage.getItem("pitsense_token");}
export function setToken(token:string|null){if(typeof window === "undefined")return;if(token)window.localStorage.setItem("pitsense_token",token);else window.localStorage.removeItem("pitsense_token");}

async function request<T>(path:string, options:RequestInit = {}, timeoutMs=30000):Promise<T>{
  const headers = new Headers(options.headers); const token=getToken(); if(token)headers.set("Authorization",`Bearer ${token}`);
  const controller=new AbortController(); const timer=window.setTimeout(()=>controller.abort(),timeoutMs);
  try { const response=await fetch(`${API}${path}`,{...options,headers,signal:options.signal||controller.signal}); const raw=await response.text(); let body:unknown={}; try{body=raw?JSON.parse(raw):{}}catch{body={}}; if(!response.ok){const envelope=(body as {error?:{message?:string;code?:string;retryable?:boolean;request_id?:string};detail?:string}).error;throw new ApiError(envelope?.message||String((body as {detail?:string}).detail||"Backend request failed."),envelope?.code||"REQUEST_FAILED",Boolean(envelope?.retryable),response.status,envelope?.request_id||response.headers.get("x-request-id")||undefined)} return body as T; }
  catch(error){if(error instanceof ApiError)throw error;if((error as Error).name==="AbortError")throw new ApiError("The backend request timed out. Please retry.","REQUEST_TIMEOUT",true,408);throw new ApiError("Backend unavailable. Start the FastAPI service and try again.","BACKEND_UNAVAILABLE",true,0)} finally{window.clearTimeout(timer)}
}

async function requestBlob(path:string, timeoutMs=60000){const headers=new Headers();const token=getToken();if(token)headers.set("Authorization",`Bearer ${token}`);const controller=new AbortController();const timer=window.setTimeout(()=>controller.abort(),timeoutMs);try{const response=await fetch(`${API}${path}`,{headers,signal:controller.signal});if(!response.ok)throw new ApiError("Audio file is unavailable.","AUDIO_UNAVAILABLE",false,response.status);return await response.blob()}catch(error){if(error instanceof ApiError)throw error;throw new ApiError("Could not download the audio file.","AUDIO_UNAVAILABLE",true)}finally{window.clearTimeout(timer)}}

export async function pollJob(jobId:string,onUpdate?:(job:AnalysisJob)=>void,signal?:AbortSignal){for(let attempt=0;attempt<360;attempt++){const job=await request<AnalysisJob>(`/jobs/${jobId}`,{signal});onUpdate?.(job);if(["completed","failed","cancelled"].includes(job.status))return job;await new Promise(resolve=>window.setTimeout(resolve,1000));}throw new ApiError("Analysis is taking longer than expected. Refresh to check the job.","ANALYSIS_TIMEOUT",true,408)}

export const api = {
  sessions:()=>request<Session[]>("/sessions"), session:(id:number)=>request<Session>(`/sessions/${id}`),
  create:(payload:{name:string;driver_name:string;circuit_name:string})=>request<Session>("/sessions",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}),
  remove:(id:number)=>request<void>(`/sessions/${id}`,{method:"DELETE"}),
  uploadAudio:(id:number,file:File)=>{const form=new FormData();form.append("audio",file);return request<AudioClip>(`/sessions/${id}/audio`,{method:"POST",body:form},120000)},
  replaceAudio:(id:number,clipId:number,file:File)=>{const form=new FormData();form.append("audio",file);return request<AudioClip>(`/sessions/${id}/audio/${clipId}/replace`,{method:"POST",body:form},120000)},
  deleteAudio:(id:number,clipId:number)=>request<void>(`/sessions/${id}/audio/${clipId}`,{method:"DELETE"}),
  audioBlob:(id:number,clipId:number)=>requestBlob(`/sessions/${id}/audio/${clipId}/file`),
  uploadCsv:(id:number,file:File)=>{const form=new FormData();form.append("csv_file",file);return request<{count:number}>(`/sessions/${id}/laps/csv`,{method:"POST",body:form},60000)},
  manualLaps:(id:number,laps:Omit<Lap,"id">[])=>request<{count:number}>(`/sessions/${id}/laps/manual`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(laps)}),
  analyse:(id:number,mode:"audio_only"|"lap_correlated")=>request<AnalysisJob>(`/sessions/${id}/analyse`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({mode})}),
  job:(jobId:string)=>request<AnalysisJob>(`/jobs/${jobId}`), cancel:(id:number)=>request<AnalysisJob>(`/sessions/${id}/analysis/cancel`,{method:"POST"}), retry:(jobId:string)=>request<AnalysisJob>(`/jobs/${jobId}/retry`,{method:"POST"}),
  timeline:(id:number)=>request<{laps:Lap[];events:TimelineEvent[];transcript:Transcript[]}>(`/sessions/${id}/timeline`),
  login:(payload:{email:string;password:string})=>request<AuthResponse>("/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}),
  register:(payload:{email:string;password:string;full_name:string;organization_name:string})=>request<AuthResponse>("/auth/register",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)}),
  me:()=>request<{authenticated:boolean;user?:{id:number;email:string;full_name:string}}>("/me"),
  exportReport:(id:number,format:"json"|"csv"|"pdf")=>requestBlob(`/sessions/${id}/exports/report.${format}`),
};

import { ArrowLeft, ArrowRight, Check, FileAudio, Info, Languages, MapPin, Mic, ShieldCheck, Square } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { submitReport, type ReportPayload } from "../../api/reports";

type Language = ReportPayload["language_hint"];

export function ReportPage() {
  const navigate = useNavigate();
  const [description, setDescription] = useState("");
  const [locality, setLocality] = useState("");
  const [language, setLanguage] = useState<Language>("en");
  const [consent, setConsent] = useState(false);
  const [synthetic, setSynthetic] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const [voiceBlob, setVoiceBlob] = useState<Blob | null>(null);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [recording, setRecording] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => () => {
    if (timerRef.current !== null) window.clearInterval(timerRef.current);
    streamRef.current?.getTracks().forEach((track) => track.stop());
  }, []);

  function stopRecording() {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }

  async function startRecording() {
    setVoiceError(null);
    setVoiceBlob(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
      setVoiceError("Voice recording is not supported here. You can continue with text.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks: BlobPart[] = [];
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
      streamRef.current = stream;
      recorderRef.current = recorder;
      setRecordingSeconds(0);
      setRecording(true);
      recorder.ondataavailable = (event) => { if (event.data.size > 0) chunks.push(event.data); };
      recorder.onstop = () => {
        if (timerRef.current !== null) window.clearInterval(timerRef.current);
        timerRef.current = null;
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        setVoiceBlob(new Blob(chunks, { type: "audio/webm" }));
        setRecording(false);
      };
      recorder.start(250);
      const startedAt = Date.now();
      timerRef.current = window.setInterval(() => {
        const elapsed = Math.min(30, Math.ceil((Date.now() - startedAt) / 1000));
        setRecordingSeconds(elapsed);
        if (elapsed >= 30 && recorder.state === "recording") recorder.stop();
      }, 250);
    } catch {
      setVoiceError("Microphone access was not available. You can continue with text.");
      setRecording(false);
    }
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await submitReport({ description, language_hint: language, locality_label: locality, consent: true, synthetic_demo_confirmation: true, ...(voiceBlob ? { voice: voiceBlob } : {}) });
      navigate(`/receipt/${result.accepted.public_id}`, { state: { capability: result.capability } });
    } catch {
      setError("We couldn’t submit the report. Check the connection and try again.");
      setSubmitting(false);
    }
  }

  return (
    <section className="mx-auto w-full max-w-5xl px-4 py-10 sm:px-6 sm:py-14 lg:px-8">
      <Link to="/" className="mb-7 inline-flex items-center gap-2 text-sm font-medium text-slate-600 no-underline hover:text-slate-950"><ArrowLeft className="size-4" /> Back to home</Link>
      <div className="mb-8 max-w-2xl">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-teal-700">Citizen report</p>
        <h1 className="mt-3 text-balance text-4xl font-semibold tracking-[-0.045em] text-slate-950 sm:text-5xl">Tell us what happened.</h1>
        <p className="mt-4 text-base leading-7 text-slate-600">Use your own words. A short description and general locality are enough.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px] lg:items-start">
        <Card className="gap-0 border-0 bg-white py-0 shadow-sm ring-slate-200">
          <CardContent className="p-5 sm:p-8">
            <form onSubmit={onSubmit} className="space-y-7">
              <div className="space-y-2.5">
                <Label htmlFor="report-description" className="text-sm font-semibold text-slate-900">What did you notice?</Label>
                <Textarea id="report-description" minLength={20} maxLength={2000} required value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Example: Water did not arrive in our lane for the last three mornings..." className="min-h-40 resize-y rounded-xl border-slate-300 bg-white px-4 py-3 text-base leading-7 shadow-none focus-visible:border-teal-700 focus-visible:ring-teal-700/15" />
                <div className="flex justify-between gap-4 text-xs text-slate-500"><span>Mention when it happened and what was affected.</span><span>{description.length}/2000</span></div>
              </div>

              <div className="grid gap-5 sm:grid-cols-[1fr_220px]">
                <div className="space-y-2.5">
                  <Label htmlFor="report-locality" className="flex items-center gap-2 text-sm font-semibold text-slate-900"><MapPin className="size-4 text-teal-700" /> General locality</Label>
                  <Input id="report-locality" minLength={3} maxLength={160} required value={locality} onChange={(event) => setLocality(event.target.value)} placeholder="e.g. Mahadevapura demo zone" className="h-11 rounded-xl border-slate-300 bg-white px-3.5 text-sm shadow-none focus-visible:border-teal-700 focus-visible:ring-teal-700/15" />
                  <p className="text-xs text-slate-500">Area or landmark only—no personal address.</p>
                </div>
                <div className="space-y-2.5">
                  <Label className="flex items-center gap-2 text-sm font-semibold text-slate-900"><Languages className="size-4 text-teal-700" /> Language</Label>
                  <Select value={language} onValueChange={(value) => setLanguage(value as Language)}>
                    <SelectTrigger className="h-11 w-full rounded-xl border-slate-300 bg-white px-3.5"><SelectValue /></SelectTrigger>
                    <SelectContent><SelectItem value="en">English</SelectItem><SelectItem value="kn">Kannada</SelectItem><SelectItem value="hi">Hindi</SelectItem><SelectItem value="mixed">Mixed language</SelectItem></SelectContent>
                  </Select>
                </div>
              </div>

              <div className={`rounded-xl border p-4 ${recording ? "border-rose-200 bg-rose-50" : voiceBlob ? "border-emerald-200 bg-emerald-50" : "border-slate-200 bg-slate-50"}`}>
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`grid size-10 place-items-center rounded-lg ${recording ? "bg-rose-100 text-rose-700" : "bg-white text-teal-700 shadow-sm"}`}>{voiceBlob ? <FileAudio className="size-5" /> : <Mic className="size-5" />}</span>
                    <div><p className="text-sm font-semibold text-slate-900">{recording ? `Recording · ${recordingSeconds}s` : voiceBlob ? `Voice attached · ${recordingSeconds}s` : "Prefer to speak?"}</p><p className="mt-0.5 text-xs text-slate-500">Optional · up to 30 seconds</p></div>
                  </div>
                  <div className="flex gap-2">
                    {recording ? <Button type="button" variant="destructive" onClick={stopRecording}><Square /> Stop</Button> : <Button type="button" variant="outline" onClick={startRecording}><Mic /> {voiceBlob ? "Record again" : "Record voice"}</Button>}
                    {voiceBlob && !recording ? <Button type="button" variant="ghost" onClick={() => setVoiceBlob(null)}>Remove</Button> : null}
                  </div>
                </div>
                {voiceError ? <p className="mt-3 text-xs font-medium text-rose-700">{voiceError}</p> : null}
              </div>

              <div className="space-y-3 rounded-xl border border-slate-200 p-4">
                <label className="flex cursor-pointer items-start gap-3 text-sm leading-5 text-slate-700"><Checkbox checked={synthetic} onCheckedChange={(checked) => setSynthetic(checked === true)} className="mt-0.5" /><span><strong className="font-semibold text-slate-900">This is an invented demo scenario.</strong><br /><span className="text-xs text-slate-500">I have not included personal information.</span></span></label>
                <label className="flex cursor-pointer items-start gap-3 text-sm leading-5 text-slate-700"><Checkbox checked={consent} onCheckedChange={(checked) => setConsent(checked === true)} className="mt-0.5" /><span>I agree to process this synthetic report for the CivicLens demonstration.</span></label>
              </div>

              {error ? <Alert variant="destructive"><Info /><AlertDescription>{error}</AlertDescription></Alert> : null}

              <div className="flex flex-col-reverse gap-3 border-t border-slate-200 pt-6 sm:flex-row sm:items-center sm:justify-between">
                <p className="flex items-center gap-2 text-xs text-slate-500"><ShieldCheck className="size-4 text-teal-700" /> Submitted as evidence, not a verified fact.</p>
                <Button type="submit" size="lg" disabled={submitting || !consent || !synthetic} className="h-11 rounded-xl px-5">{submitting ? "Submitting…" : "Submit report"}{!submitting ? <ArrowRight /> : null}</Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <aside className="space-y-4 lg:sticky lg:top-24">
          <Card className="gap-0 border-0 bg-[#12363a] py-0 text-white ring-0"><CardContent className="p-5"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-teal-200">What happens next</p><ol className="mt-5 space-y-4">{["Your report is received", "Related reports may be grouped", "An officer reviews the evidence"].map((item, index) => <li key={item} className="flex gap-3 text-sm text-slate-200"><span className="grid size-6 shrink-0 place-items-center rounded-full bg-white/10 text-xs font-semibold">{index + 1}</span><span className="pt-0.5">{item}</span></li>)}</ol></CardContent></Card>
          <div className="flex gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-900"><Info className="mt-0.5 size-4 shrink-0" /><p><strong>This is not an emergency service.</strong> This prototype accepts synthetic reports only.</p></div>
        </aside>
      </div>
    </section>
  );
}

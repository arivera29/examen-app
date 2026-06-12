import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  AttemptAnswersReport,
  Exam,
  ExamReport,
  ExamSession,
  Invitation,
  Question,
  QuestionBank,
  PaginatedQuestions,
  QuestionBackupRestoreResult,
  Topic,
} from '../models';

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiUrl;

  getQuestionBanks(): Observable<QuestionBank[]> {
    return this.http.get<QuestionBank[]>(`${this.baseUrl}/question-banks`);
  }

  createQuestionBank(name: string, description: string): Observable<QuestionBank> {
    return this.http.post<QuestionBank>(`${this.baseUrl}/question-banks`, { name, description });
  }

  updateQuestionBank(bankId: string, name: string, description: string): Observable<QuestionBank> {
    return this.http.put<QuestionBank>(`${this.baseUrl}/question-banks/${bankId}`, { name, description });
  }

  deleteQuestionBank(bankId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/question-banks/${bankId}`);
  }

  getQuestions(bankId: string, page = 1, pageSize = 10): Observable<PaginatedQuestions> {
    return this.http.get<PaginatedQuestions>(
      `${this.baseUrl}/question-banks/${bankId}/questions`,
      { params: { page, page_size: pageSize } }
    );
  }

  createQuestion(bankId: string, data: FormData): Observable<Question> {
    return this.http.post<Question>(`${this.baseUrl}/question-banks/${bankId}/questions`, data);
  }

  updateQuestion(bankId: string, questionId: string, data: FormData): Observable<Question> {
    return this.http.put<Question>(
      `${this.baseUrl}/question-banks/${bankId}/questions/${questionId}`,
      data
    );
  }

  deleteQuestion(bankId: string, questionId: string): Observable<void> {
    return this.http.delete<void>(
      `${this.baseUrl}/question-banks/${bankId}/questions/${questionId}`
    );
  }

  downloadQuestionBackup(bankId: string): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/question-banks/${bankId}/questions/backup`, {
      responseType: 'blob',
    });
  }

  restoreQuestionBackup(
    bankId: string,
    file: File,
    mode: 'append' | 'replace'
  ): Observable<QuestionBackupRestoreResult> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('mode', mode);
    return this.http.post<QuestionBackupRestoreResult>(
      `${this.baseUrl}/question-banks/${bankId}/questions/restore`,
      formData
    );
  }

  getTopics(): Observable<Topic[]> {
    return this.http.get<Topic[]>(`${this.baseUrl}/topics`);
  }

  createTopic(name: string, description: string): Observable<Topic> {
    return this.http.post<Topic>(`${this.baseUrl}/topics`, { name, description });
  }

  updateTopic(topicId: string, name: string, description: string): Observable<Topic> {
    return this.http.put<Topic>(`${this.baseUrl}/topics/${topicId}`, { name, description });
  }

  deleteTopic(topicId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/topics/${topicId}`);
  }

  getExams(): Observable<Exam[]> {
    return this.http.get<Exam[]>(`${this.baseUrl}/exams`);
  }

  createExam(data: Record<string, unknown>): Observable<Exam> {
    return this.http.post<Exam>(`${this.baseUrl}/exams`, data);
  }

  updateExam(examId: string, data: Record<string, unknown>): Observable<Exam> {
    return this.http.put<Exam>(`${this.baseUrl}/exams/${examId}`, data);
  }

  deleteExam(examId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/exams/${examId}`);
  }

  inviteToExam(examId: string, emails: string[]): Observable<Invitation[]> {
    return this.http.post<Invitation[]>(`${this.baseUrl}/exams/${examId}/invite`, { emails });
  }

  getExamInvitations(examId: string): Observable<Invitation[]> {
    return this.http.get<Invitation[]>(`${this.baseUrl}/exams/${examId}/invitations`);
  }

  deleteExamInvitation(examId: string, invitationId: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/exams/${examId}/invitations/${invitationId}`);
  }

  resendExamInvitation(examId: string, invitationId: string): Observable<Invitation> {
    return this.http.post<Invitation>(
      `${this.baseUrl}/exams/${examId}/invitations/${invitationId}/resend`,
      {}
    );
  }

  getExamReport(examId: string): Observable<ExamReport> {
    return this.http.get<ExamReport>(`${this.baseUrl}/exams/${examId}/report`);
  }

  downloadExamReportExport(examId: string): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/exams/${examId}/report/export`, {
      responseType: 'blob',
    });
  }

  deleteInviteeExamResults(examId: string, inviteeEmail: string): Observable<{ deleted_attempts: number }> {
    return this.http.delete<{ deleted_attempts: number }>(
      `${this.baseUrl}/exams/${examId}/invitee-results`,
      { params: { email: inviteeEmail } }
    );
  }

  getAttemptAnswersReport(examId: string, attemptId: string): Observable<AttemptAnswersReport> {
    return this.http.get<AttemptAnswersReport>(
      `${this.baseUrl}/exams/${examId}/attempts/${attemptId}/answers`
    );
  }

  getExamSessionInfo(token: string): Observable<Record<string, unknown>> {
    return this.http.get<Record<string, unknown>>(`${this.baseUrl}/exam-session/${token}`);
  }

  startExamSession(token: string, cameraVerified: boolean, fullName: string): Observable<ExamSession> {
    return this.http.post<ExamSession>(`${this.baseUrl}/exam-session/${token}/start`, {
      camera_verified: cameraVerified,
      full_name: fullName.trim(),
    });
  }

  submitAnswer(
    attemptId: string,
    questionId: string,
    selectedOptionIds: string[],
    openText?: string
  ): Observable<unknown> {
    return this.http.post(`${this.baseUrl}/attempts/${attemptId}/answers`, {
      question_id: questionId,
      selected_option_ids: selectedOptionIds,
      open_text: openText,
    });
  }

  submitExam(attemptId: string, skipVideoRequired = false): Observable<unknown> {
    return this.http.post(`${this.baseUrl}/attempts/${attemptId}/submit`, {
      skip_video_required: skipVideoRequired,
    });
  }

  saveAttemptProgress(
    attemptId: string,
    currentQuestionIndex: number,
    lockedQuestionIds: string[]
  ): Observable<{ current_question_index: number; locked_question_ids: string[] }> {
    return this.http.put<{ current_question_index: number; locked_question_ids: string[] }>(
      `${this.baseUrl}/attempts/${attemptId}/progress`,
      {
        current_question_index: currentQuestionIndex,
        locked_question_ids: lockedQuestionIds,
      }
    );
  }

  finishExamSession(token: string): Observable<{ final_score: number | null; attempt_number: number }> {
    return this.http.post<{ final_score: number | null; attempt_number: number }>(
      `${this.baseUrl}/exam-session/${token}/finish`,
      {}
    );
  }

  reportTabSwitchViolation(token: string): Observable<{
    final_score: number | null;
    attempt_number: number | null;
    exam_finalized: boolean;
    terminated_for_violation: boolean;
    message: string;
  }> {
    return this.http.post<{
      final_score: number | null;
      attempt_number: number | null;
      exam_finalized: boolean;
      terminated_for_violation: boolean;
      message: string;
    }>(`${this.baseUrl}/exam-session/${token}/tab-switch-violation`, {});
  }

  sendProctoringData(attemptId: string, frame: Blob, mouseEvents: unknown[]): Observable<unknown> {
    const formData = new FormData();
    formData.append('frame', frame, 'frame.jpg');
    formData.append('mouse_events', JSON.stringify(mouseEvents));
    return this.http.post(`${this.baseUrl}/attempts/${attemptId}/proctoring`, formData);
  }

  uploadAttemptSnapshot(
    attemptId: string,
    snapshotType: 'start' | 'progress',
    frame: Blob
  ): Observable<unknown> {
    const formData = new FormData();
    formData.append('snapshot_type', snapshotType);
    formData.append('frame', frame, 'snapshot.jpg');
    return this.http.post(`${this.baseUrl}/attempts/${attemptId}/snapshots`, formData);
  }

  uploadAttemptVideo(attemptId: string, video: Blob): Observable<{ video_url: string }> {
    const formData = new FormData();
    formData.append('video', video, 'attempt.webm');
    return this.http.post<{ video_url: string }>(
      `${this.baseUrl}/attempts/${attemptId}/video`,
      formData
    );
  }
}

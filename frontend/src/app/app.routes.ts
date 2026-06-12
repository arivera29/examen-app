import { Routes } from '@angular/router';
import { authGuard, guestGuard } from './core/guards/auth.guard';
import { LoginComponent } from './features/auth/login/login.component';
import { RegisterComponent } from './features/auth/register/register.component';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { HomeComponent } from './features/dashboard/home/home.component';
import { QuestionBanksComponent } from './features/question-banks/question-banks.component';
import { BankDetailComponent } from './features/question-banks/bank-detail/bank-detail.component';
import { ExamsComponent } from './features/exams/exams.component';
import { ExamInviteComponent } from './features/exams/exam-invite/exam-invite.component';
import { ExamReportComponent } from './features/exams/exam-report/exam-report.component';
import { MfaSetupComponent } from './features/auth/mfa-setup/mfa-setup.component';
import { TopicsComponent } from './features/topics/topics.component';
import { ExamTakeComponent } from './features/exam-take/exam-take.component';

export const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
  { path: 'login', component: LoginComponent, canActivate: [guestGuard] },
  { path: 'register', component: RegisterComponent, canActivate: [guestGuard] },
  { path: 'exam/take/:token', component: ExamTakeComponent },
  {
    path: 'dashboard',
    component: DashboardComponent,
    canActivate: [authGuard],
    children: [
      { path: '', component: HomeComponent },
      { path: 'banks', component: QuestionBanksComponent },
      { path: 'banks/:id', component: BankDetailComponent },
      { path: 'topics', component: TopicsComponent },
      { path: 'exams', component: ExamsComponent },
      { path: 'exams/:id/invite', component: ExamInviteComponent },
      { path: 'exams/:id/report', component: ExamReportComponent },
      { path: 'mfa', component: MfaSetupComponent },
    ],
  },
  { path: '**', redirectTo: 'dashboard' },
];

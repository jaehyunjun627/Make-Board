<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
<%@ taglib prefix="c" uri="http://java.sun.com/jsp/jstl/core"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<link
	href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"
	rel="stylesheet">
<link rel="stylesheet" type="text/css" href="./css/board.css">
<script
	src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<title>답글 작성</title>
</head>
<body>
	<div id="container">
		<center>
			<h2>📝 답글 작성하기</h2>
			<p>
				원글: <strong>${bean.subject}</strong>
			</p>
			<hr />

			<form action="BoardRewriteProcCon.do" method="post">
				<!-- 답글 처리에 필요한 hidden 값들 -->
				<input type="hidden" name="num" value="${NUM}" />
				<!-- 여기 주의!!!!!!!!!!! -->
				<input type="hidden" name="ref" value="${REF}" /> <input
					type="hidden" name="re_step" value="${RE_STEP}" /> <input
					type="hidden" name="re_level" value="${RE_LEVEL}" />

				<table class="table table-striped table-bordered table-hover">
					<tbody>
						<tr height="50">
							<th width="150" align="center">작성자</th>
							<td width="400" align="left">
	<!-- 여기 주의!!!!!!!!!!! --> <input type="text" name="writer"
								size="60" style="background: transparent;" required />
							</td>
						</tr>

						<tr height="50">
							<th width="150" align="center">제목</th>
							<td width="400" align="left"><input type="text"
								name="subject" size="60" value="Re: ${bean.subject}"
								style="background: transparent" required /></td>
						</tr>

						<tr height="50">
							<th width="150" align="center">이메일</th>
							<td width="400" align="left"><input type="email"
								name="email" size="60" style="background: transparent" /></td>
						</tr>

						<tr height="50">
							<th width="150" align="center">비밀번호</th>
							<td width="400" align="left"><input type="password"
								name="password" size="60" style="background: transparent"
								required /></td>
						</tr>

						<tr height="50">
							<th width="150" align="center">글내용</th>
							<td width="400" align="left"><textarea rows="10" cols="50"
									name="content" required>

                                </textarea></td>
						</tr>

						<tr height="50">
							<th align="center" colspan="2"><input type="submit"
								value="답글등록" class="btn btn-primary" />&nbsp;&nbsp; <input
								type="reset" value="다시작성" class="btn btn-secondary" />&nbsp;&nbsp;
								<button type="button" class="btn btn-outline-secondary"
									onclick="location.href='BoardListCon.do'">목록보기</button></th>
						</tr>
					</tbody>
					
				</table>
			</form>
		</center>
	</div>
</body>
</html>
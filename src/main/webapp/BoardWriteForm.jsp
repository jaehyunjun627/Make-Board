<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>

<%@ taglib prefix='c' uri="http://java.sun.com/jsp/jstl/core"%>
<%@ taglib prefix='fmt' uri="http://java.sun.com/jsp/jstl/fmt"%>
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
<title>BBS Write</title>
</head>
<body>
	<div id="container">
		<h2>게시글 입력하기</h2>
		<p></p>
		<form action="BoardWriteProcCon.do" method="post"><!-- ~~~~~~여기가 백으로 보내는 핵심 ~~~~~~!-->
			<center>
				<table class="table table-striped table-bordered table-hover">
					<tbody>
						<tr height="50">
							<th width="150" align="center">작성자</th>
							<td width="400" align="left"><input type="text" name="writer"
								size="60" style="background: transparent" /></td>
						</tr>
						<tr height="50">
							<th width="150" align="center">제목</th>
							<td width="400" align="left"><input type="text"
								name="subject" size="60" style="background: transparent">
							</td>
						</tr>

						<tr height="50">
							<th width="150" align="center">이메일</th>
							<td width="400" align="left"><input type="email"
								name="email" size="60" style="background: transparent">
							</td>
						</tr>

						<tr height="50">
							<th width="150" align="center">비밀번호</th>
							<td width="400" align="left"><input type="password"
								name="password" size="60" style="background: transparent">
							</td>
						</tr>

						<tr height="50">
							<th width="150" align="center">글내용</th>
							<td width="400" align="left"><textarea rows="10" cols="50"
									name="content"></textarea></td>
						</tr>

						<tr height="50">
							<th align="center" colspan="2"><input type="submit"
								value="글쓰기">&nbsp;&nbsp; <input type="reset"
								value="다시작성"> &nbsp;&nbsp;
								<button type="button" onclick="location.href='BoardListCon.do'">목록보기</button></th> <!-- 여기도 자바로 보내는 부분 -->
								
						</tr>
					</tbody>

				</table>
			</center>
		</form>
	</div>


</body>
</html>
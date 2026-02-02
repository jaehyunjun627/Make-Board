<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<link
	href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css"
	rel="stylesheet">
<link rel="stylesheet" type="text/css" href="./css/board.css">
<script
	src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<title>BoardDeleteForm</title>
</head>
<body>
	<center>
		<h2>게시글 삭제 하기</h2>
		<form action="BoardDeleteProcCon.do" method="post">
			<table border="1" width="600"
				class="table table-striped table-bordered table-hover">
				
				<tr height="40">
					<td width="150" align="center">패스워드</td>
					<td width="450" colspan="3">&nbsp;
						<input type="password" name="PASSWORD" size="60" style="border: none; background: transparent" />
					</td>
				</tr>
				
				<tr height="40">
					<td colspan="4" align="center">
					    <input type="hidden" name="NUM" value="${bean.NUM }" >
					    <input type="hidden" name="pass" value="${bean.PASSWORD }" >
						<input type="submit" value="글삭제" >&nbsp;&nbsp;
						<input type="button" onclick="location.href='BoardListCon.do'" value="전체글보기">
					</td>
				</tr>

			</table>
		</form>
	</center>
</body>
</html>
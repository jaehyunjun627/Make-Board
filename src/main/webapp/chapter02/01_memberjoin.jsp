<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>회원가입</title>
<link rel="stylesheet" type= "text/css" href="../css/join.css" />
</head>
<body>

	<center>
		<h2>회원 가입</h2>
		<form action="memberjoinproc.jsp" method="post">
			<table width="500" border="1">
				<tr height="40">
					<td width="200" align="center">아이디</td>
					<td width="400" align="center"><input type="text" name="id"
						size="40" placeholder="id를 입력하세요"></td>
				</tr>
				<tr height="40">
					<td width="200" align="center">패스워드</td>
					<td width="400" align="center"><input type="password"
						name="pass" size="40" placeholder="패스워드를 입력하세요"></td>
				</tr>
				<tr height="40">
					<td width="200" align="center">이메일</td>
					<td width="400" align="center"><input type="email"
						name="email" size="40"></td>
				</tr>
				<tr height="40">
					<td width="200" align="center">전화번호</td>
					<td width="400" align="center"><input type="phone" name="tel"
						size="40"></td>
				</tr>

				<tr height="40">
					<td width="200" align="center">주소</td>
					<td width="400" align="center"><input type="text"
						name="address" size="40"></td>
				</tr>

				<tr height="50">
					<td align="center" colspan="2"><input type="submit"
						value="회원가입"></td>
				</tr>
			</table>
		</form>
</body>
</html>
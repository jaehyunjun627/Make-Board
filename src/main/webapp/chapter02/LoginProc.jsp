<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>Account</title>
<style>
body {
	font-family: Arial, sans-serif;
	background-color: #f5f5dc;
	margin: 0;
	padding: 0;
	display: flex;
	justify-content: center;
	align-items: center;
	height: 100vh;
}

.container {
	background-color: #fff;
	padding: 20px;
	border-radius: 8px;
	box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
	text-align: center;
	width: 400px;
}

h2 {
	margin-bottom: 20px;
}

hr {
	margin: 20px 0;
}

.message {
	font-size: 18px;
	margin-bottom: 20px;
}
</style>
</head>
<body>
	<!-- class: LoginDAO id= login
 -->
	<jsp:useBean id="login" class="model.LoginDAO" scope="page" />
	<jsp:setProperty name="login" property="*" />

	<div align="center">
		<h2>로그인</h2>
		<hr />
		<%
		if (login.checkUser()) {
			out.println("로그인 성공");
		} else {
			out.println("로그인 실패");
		}
		%>
		<hr />
		고객의 아이디
		<jsp:getProperty property="userid" name="login" />
		고객의 비밀번호
		<jsp:getProperty property="password" name="login" />

	</div>
</body>
</html>
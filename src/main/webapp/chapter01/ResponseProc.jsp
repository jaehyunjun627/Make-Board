<%@page import="javax.swing.text.Document"%>
<%@ page language="java" contentType="text/html; charset=UTF-8"
	pageEncoding="UTF-8"%>
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>ResponceProc</title>
</head>
<body>
	<%
	//오라클에 저장된 데이터로 가설

	String dbid = "soldesk";
	String dbpass = "12345";

	//request 객체 id, pass 받아오기
	String id = request.getParameter("id");
	String pass = request.getParameter("pass");

	if (dbid.equals(id) && dbpass.equals(pass)) {
		session.setAttribute("id", id);
		session.setAttribute("pass", pass);
		
		response.sendRedirect("ResponseLogin.jsp");

	} else {
	%>
	<script>
		alert("아이디와 비밀번호가 일치하지 않습니다")
		history.go(-1);
	</script>

	<%
	}
	%>
	
	여기는 안닿는 코드
</body>
</html>
<%@page import="model.MemberDTO"%>
<%@page import="model.MemberDAO"%>
<%@ page language="java" contentType="text/html; charset=UTF-8"
    pageEncoding="UTF-8"%>
<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>delete</title>

<link rel="stylesheet" type="text/css" href="../css/member.css">

</head>
<body>

<%
String id = request.getParameter("id");
MemberDAO mdao = new MemberDAO();
MemberDTO mbean = mdao.oneSelectMember(id);

%>

<center>
		<h2>회원 정보 수정하기</h2>
		<form action="MemberDeleteProc.jsp" method="get">
		<table width="400" border="1">
			<tr height="40">
			<td align="center" width="150">아이디</td>
			<td width="250"><%=mbean.getId() %></td>
		</tr>
		
					<tr height="40">
			<td align="center" width="150">패스워드</td>
			<td width="250">
			<input type="password" name="pass1"  placeholder="비밀번호 확인"/>  <!-- input 있어야 가져감 -->
			</td>
		</tr>
		
		
			<tr height="40">
			<td align="center" colspan="2">
			<!-- 데이터베이스에서 가져온 id 숨겨서 보내기  id는 input안함 -->
			<input type="hidden" name="id" value="<%=id%>"/> 
			<input type="submit" value="수정완료"/>
			<p></p>
			<input type="button" value="전체회원보기" onclick="location.href='MemberList.jsp'" />
			</td>
			
		</tr>
		
		</table>
		</form>
	</center>

</body>
</html>